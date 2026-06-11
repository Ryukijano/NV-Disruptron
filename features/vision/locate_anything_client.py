"""LocateAnything-3B client with Nemotron Omni grounding fallback.

Follows the official LocateAnythingWorker pattern from the model card:
  - bfloat16 dtype for best accuracy / memory balance
  - Chat-template API via processor.py_apply_chat_template()
  - process_vision_info() for proper image preprocessing
  - Parallel Box Decoding (hybrid mode) for fast inference
  - Video frame-sampling + temporal tracking for CCTV streams

Usage (single image):
    client = get_vision_client()
    result = client.detect(image, ["blocked pavement", "broken lift", "flooding"])

Usage (video stream):
    result = client.detect_video_stream(
        image_url="https://jamcams.tfl.gov.uk/00001.02151.jpg",
        labels=["car", "bus", "person"],
        sample_interval_sec=2.0,
        max_frames=30,
    )
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure HuggingFace cache dirs are writable before importing transformers
os.environ.setdefault("HF_MODULES_CACHE", "/tmp/hf_modules_cache_aimsgroupuol")
os.environ.setdefault("HF_HOME", "/tmp/hf_home_aimsgroupuol")

# Optional LocateAnything via transformers
try:
    import torch
    from transformers import AutoModel, AutoProcessor, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Optional Nemotron fallback via OpenAI-compatible API
import httpx


NEMOTRON_URL = os.getenv("NEMOTRON_URL", "http://localhost:8008/v1")


@dataclass(frozen=True)
class DetectionResult:
    label: str
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    confidence: float


class LocateAnythingClient:
    """Thin wrapper around LocateAnything-3B or Nemotron Omni grounding."""

    def __init__(
        self,
        model_id: str = "nvidia/LocateAnything-3B",
        device: str = "cuda",
        fallback_to_nemotron: bool = True,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.fallback = fallback_to_nemotron
        self._model: Any = None
        self._processor: Any = None
        self._tokenizer: Any = None
        self._available = False

        if TRANSFORMERS_AVAILABLE:
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    model_id, trust_remote_code=True
                )
                self._processor = AutoProcessor.from_pretrained(
                    model_id, trust_remote_code=True
                )
                self._model = AutoModel.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    torch_dtype=torch.bfloat16,
                    low_cpu_mem_usage=True,
                ).to(device)
                self._model.eval()
                self._available = True
                print("LocateAnything-3B loaded (bfloat16, hybrid PBD)")
            except Exception as exc:
                print(f"LocateAnything-3B load failed: {exc}")
                self._available = False

    def is_available(self) -> bool:
        return self._available

    def detect(
        self,
        image: Any,
        labels: list[str],
        confidence_threshold: float = 0.3,
    ) -> list[DetectionResult]:
        """Open-vocab object detection.

        Args:
            image: PIL Image or path to image file.
            labels: List of labels to detect (e.g. ["blocked pavement", "broken lift"]).
            confidence_threshold: Min confidence [0,1].

        Returns:
            List of DetectionResult with normalized bboxes.
        """
        if self._available and self._model is not None and self._processor is not None:
            return self._detect_locate_anything(image, labels, confidence_threshold)

        if self.fallback:
            return self._detect_nemotron(image, labels, confidence_threshold)

        return []

    def ground_multi(
        self,
        image: Any,
        query: str,
        confidence_threshold: float = 0.3,
    ) -> list[DetectionResult]:
        """Phrase grounding (e.g. 'people wearing red shirts')."""
        return self._predict_and_parse(image, query, confidence_threshold)

    def detect_video_stream(
        self,
        image_url: str,
        labels: list[str],
        sample_interval_sec: float = 2.0,
        max_frames: int = 30,
        confidence_threshold: float = 0.3,
        temporal_smoothing: int = 3,
        iou_threshold: float = 0.5,
    ) -> dict:
        """Process a live CCTV feed by polling the image URL and tracking objects temporally.

        Args:
            image_url: URL of the camera snapshot (e.g. TfL JamCam JPG).
            labels: Categories to detect.
            sample_interval_sec: Seconds between frame captures.
            max_frames: Max frames to process before returning.
            confidence_threshold: Per-frame detection threshold.
            temporal_smoothing: Min number of frames an object must appear in to be kept.
            iou_threshold: IoU threshold for associating boxes across frames.

        Returns:
            Dict with keys: detections (list), frame_count, tracked_objects, duration_sec.
        """
        from PIL import Image
        import urllib.request

        if not self._available:
            return {"detections": [], "frame_count": 0, "tracked_objects": [], "error": "model not available"}

        all_frame_results: list[list[DetectionResult]] = []
        start_time = time.time()

        for frame_idx in range(max_frames):
            frame_start = time.time()
            try:
                with urllib.request.urlopen(image_url, timeout=10) as resp:
                    img = Image.open(io.BytesIO(resp.read())).convert("RGB")
            except Exception as exc:
                print(f"Frame {frame_idx}: fetch failed: {exc}")
                break

            cats = "</c>".join(labels)
            prompt = f"Locate all the instances that matches the following description: {cats}."
            frame_results = self._predict_and_parse(img, prompt, confidence_threshold)
            all_frame_results.append(frame_results)
            print(f"Frame {frame_idx}: {len(frame_results)} detections")

            # Sleep until next sample
            elapsed = time.time() - frame_start
            sleep_for = max(0, sample_interval_sec - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

        # --- Temporal tracking: associate boxes across frames ---
        tracked = self._track_temporally(all_frame_results, iou_threshold)
        # --- Smoothing: keep only objects seen in >= temporal_smoothing frames ---
        smoothed = [t for t in tracked if t["frame_count"] >= temporal_smoothing]

        duration = time.time() - start_time
        return {
            "detections": smoothed,
            "frame_count": len(all_frame_results),
            "tracked_objects": len(tracked),
            "duration_sec": round(duration, 2),
        }

    def _predict_and_parse(
        self,
        image: Any,
        prompt: str,
        threshold: float,
    ) -> list[DetectionResult]:
        """Core inference using the official LocateAnythingWorker pattern."""
        from PIL import Image

        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        # Official pattern: messages -> chat template -> process_vision_info -> generate
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        images, videos = self._processor.process_vision_info(messages)
        inputs = self._processor(
            text=[text],
            images=images,
            videos=videos,
            return_tensors="pt",
        ).to(self.device)

        pixel_values = inputs["pixel_values"].to(torch.bfloat16)
        input_ids = inputs["input_ids"]
        image_grid_hws = inputs.get("image_grid_hws", None)

        with torch.no_grad():
            response = self._model.generate(
                pixel_values=pixel_values,
                input_ids=input_ids,
                attention_mask=inputs["attention_mask"],
                image_grid_hws=image_grid_hws,
                tokenizer=self._tokenizer,
                max_new_tokens=256,
                use_cache=True,
                generation_mode="hybrid",
                n_future_tokens=6,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1,
            )

        answer = response[0] if isinstance(response, tuple) else response
        results = self._parse_boxes(answer, threshold)
        return results

    def _detect_locate_anything(
        self,
        image: Any,
        labels: list[str],
        threshold: float,
    ) -> list[DetectionResult]:
        """Object detection using the official prompt template."""
        cats = "</c>".join(labels)
        prompt = f"Locate all the instances that matches the following description: {cats}."
        return self._predict_and_parse(image, prompt, threshold)

    def _detect_nemotron(
        self,
        image: Any,
        labels: list[str],
        threshold: float,
    ) -> list[DetectionResult]:
        """Nemotron Omni grounding fallback via OpenAI-compatible API."""
        from PIL import Image

        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        label_text = ", ".join(labels)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Detect and localize all instances of: {label_text}. "
                            f"Return JSON array: {{'detections': ["
                            f"{{'label': str, 'bbox': [x1,y1,x2,y2], 'confidence': float}}]}}"
                        ),
                    },
                ],
            }
        ]

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{NEMOTRON_URL}/chat/completions",
                    json={
                        "model": "nemotron-omni",
                        "messages": messages,
                        "max_tokens": 512,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Extract JSON from content
                parsed = self._extract_json(content)
                detections = parsed.get("detections", [])
                return [
                    DetectionResult(
                        label=d["label"],
                        bbox=d["bbox"],
                        confidence=d.get("confidence", 0.5),
                    )
                    for d in detections
                    if d.get("confidence", 0) >= threshold
                ]
        except Exception as exc:
            print(f"Nemotron fallback detection failed: {exc}")
            return []

    @staticmethod
    def _parse_boxes(answer: str, threshold: float) -> list[DetectionResult]:
        """Parse LocateAnything output with <ref>label</ref><box><x1><y1><x2><y2></box> format.

        The model outputs pairs like:
            <ref>car</ref><box><456><357><511><397></box>
            <ref>bus</ref><box>None</box>
        We extract the label from the nearest preceding <ref> tag and skip <box>None</box>.
        """
        results: list[DetectionResult] = []

        # Find all <ref>label</ref> and <box>...</box> positions
        ref_pattern = re.compile(r"<ref>([^<]+)</ref>")
        box_pattern = re.compile(r"<box>(?:(?:<(\d+)><(\d+)><(\d+)><(\d+)>)|None)</box>")

        refs = [(m.start(), m.end(), m.group(1)) for m in ref_pattern.finditer(answer)]
        boxes = [(m.start(), m.end(), m.groups()) for m in box_pattern.finditer(answer)]

        for box_start, box_end, groups in boxes:
            if groups[0] is None:
                # <box>None</box> — skip
                continue
            x1, y1, x2, y2 = [int(g) / 1000.0 for g in groups]
            # Find nearest preceding <ref> tag
            label = "object"
            for ref_start, ref_end, ref_label in reversed(refs):
                if ref_end <= box_start:
                    label = ref_label
                    break
            results.append(DetectionResult(label=label, bbox=[x1, y1, x2, y2], confidence=0.85))
        return results

    @staticmethod
    def _track_temporally(
        frame_results: list[list[DetectionResult]],
        iou_threshold: float = 0.5,
    ) -> list[dict]:
        """Simple IoU-based temporal tracking across frames.

        Returns list of tracked objects with aggregated bboxes and frame counts.
        """
        import numpy as np

        def _iou(box_a: list[float], box_b: list[float]) -> float:
            x1 = max(box_a[0], box_b[0])
            y1 = max(box_a[1], box_b[1])
            x2 = min(box_a[2], box_b[2])
            y2 = min(box_a[3], box_b[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
            area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
            union = area_a + area_b - inter
            return inter / union if union > 0 else 0.0

        tracks: list[dict] = []
        for frame_idx, detections in enumerate(frame_results):
            for det in detections:
                matched = False
                for track in tracks:
                    if track["label"] == det.label and _iou(track["bbox"], det.bbox) >= iou_threshold:
                        # Update track with exponential moving average
                        alpha = 0.3
                        track["bbox"] = [
                            track["bbox"][i] * (1 - alpha) + det.bbox[i] * alpha
                            for i in range(4)
                        ]
                        track["frame_count"] += 1
                        track["confidence"] = max(track["confidence"], det.confidence)
                        track["last_seen"] = frame_idx
                        matched = True
                        break
                if not matched:
                    tracks.append({
                        "label": det.label,
                        "bbox": list(det.bbox),
                        "confidence": det.confidence,
                        "frame_count": 1,
                        "first_seen": frame_idx,
                        "last_seen": frame_idx,
                    })
        return tracks

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON object from markdown/text response."""
        import re

        # Try fenced code block first
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            return json.loads(m.group(1))
        # Try raw JSON object
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        return {}


def get_vision_client() -> LocateAnythingClient:
    """Factory: returns a configured LocateAnythingClient with sensible defaults."""
    # Run on GPU alongside vLLM Nemotron; max_tokens reduced to free KV cache space.
    device = "cuda"
    return LocateAnythingClient(device=device, fallback_to_nemotron=True)


# Lazy singleton
_client: LocateAnythingClient | None = None


def get_client() -> LocateAnythingClient:
    global _client
    if _client is None:
        _client = get_vision_client()
    return _client
