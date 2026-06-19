"""LocateAnything-3B vision client for the HF Space backend.

Loads the model lazily on first request and exposes lightweight detection / grounding
endpoints. Falls back to Nemotron Omni if LocateAnything is not available.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# Optional LocateAnything via transformers
try:
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor, AutoTokenizer

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


NEMOTRON_URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
LOCATEANYTHING_MODEL = os.environ.get("LOCATEANYTHING_MODEL", "nvidia/LocateAnything-3B")


@dataclass(frozen=True)
class DetectionResult:
    label: str
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    confidence: float


class LocateAnythingClient:
    """Stateful worker that loads LocateAnything-3B once and serves vision queries."""

    def __init__(
        self,
        model_id: str = LOCATEANYTHING_MODEL,
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

        self._load()

    def _load(self) -> None:
        if not TRANSFORMERS_AVAILABLE:
            return
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._processor = AutoProcessor.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._model = AutoModel.from_pretrained(
                self.model_id,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=True,
            ).to(self.device)
            self._model.eval()
            self._available = True
        except Exception as exc:
            print(f"LocateAnything-3B load failed: {exc}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def detect(
        self,
        image: Image.Image | str | Path,
        labels: list[str],
        confidence_threshold: float = 0.3,
    ) -> list[DetectionResult]:
        if self._available and self._model is not None and self._processor is not None:
            return self._detect_locate_anything(image, labels, confidence_threshold)
        if self.fallback:
            return self._detect_nemotron(image, labels, confidence_threshold)
        return []

    def _detect_locate_anything(
        self,
        image: Image.Image | str | Path,
        labels: list[str],
        threshold: float,
    ) -> list[DetectionResult]:
        cats = "</c>".join(labels)
        prompt = f"Locate all the instances that matches the following description: {cats}."
        return self._predict_and_parse(image, prompt, threshold)

    def _predict_and_parse(
        self,
        image: Image.Image | str | Path,
        prompt: str,
        threshold: float,
    ) -> list[DetectionResult]:
        from PIL import Image

        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

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
        return self._parse_boxes(answer, threshold)

    def _detect_nemotron(
        self,
        image: Image.Image | str | Path,
        labels: list[str],
        threshold: float,
    ) -> list[DetectionResult]:
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
                            "Return JSON object: {'detections': [{'label': str, 'bbox': [x1,y1,x2,y2], 'confidence': float}]}"
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
                content = resp.json()["choices"][0]["message"]["content"]
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
        results: list[DetectionResult] = []
        ref_pattern = re.compile(r"<ref>([^<]+)</ref>")
        box_pattern = re.compile(r"<box>(?:(?:<(\d+)><(\d+)><(\d+)><(\d+)>)|None)</box>")

        refs = [(m.start(), m.end(), m.group(1)) for m in ref_pattern.finditer(answer)]
        boxes = [(m.start(), m.end(), m.groups()) for m in box_pattern.finditer(answer)]

        for box_start, _box_end, groups in boxes:
            if groups[0] is None:
                continue
            x1, y1, x2, y2 = [int(g) / 1000.0 for g in groups]
            label = "object"
            for ref_start, ref_end, ref_label in reversed(refs):
                if ref_end <= box_start:
                    label = ref_label
                    break
            results.append(DetectionResult(label=label, bbox=[x1, y1, x2, y2], confidence=0.85))
        return results

    @staticmethod
    def _extract_json(text: str) -> dict:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            return json.loads(m.group(1))
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        return {}


_client: LocateAnythingClient | None = None


def get_vision_client() -> LocateAnythingClient:
    """Lazy singleton for the LocateAnything client."""
    global _client
    if _client is None:
        _client = LocateAnythingClient()
    return _client
