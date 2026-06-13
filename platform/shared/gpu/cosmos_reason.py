"""NVIDIA Cosmos Reason 2 video reasoning VLM for CCTV clip analysis.

Unlike LocateAnything-3B (per-frame open-vocab detection), Cosmos Reason 2
reasons over short video clips to produce causal explanations:
"Why did the crowd form?", "Is the flooding getting worse?", etc.

Usage:
    from shared.gpu.cosmos_reason import CosmosReasonClient
    client = CosmosReasonClient()
    analysis = client.analyze_clip(video_path="/tmp/cctv_clip.mp4", question="What is happening?")
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

COSMOS_AVAILABLE = False
try:
    from cosmos1.models.diffusion.nemo import inference
    COSMOS_AVAILABLE = True
except Exception:
    pass

# Cosmos3 Omni action-forward dynamics (secondary)
COSMOS3_AVAILABLE = False
try:
    import cosmos3_omni
    COSMOS3_AVAILABLE = True
except Exception:
    pass


class CosmosReasonClient:
    """Client for Cosmos Reason 2 video reasoning over CCTV clips."""

    def __init__(
        self,
        model_name: str = "cosmos-reason-2-7b",
        inference_server: str | None = None,  # NIM endpoint
        local_model_path: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.inference_server = inference_server or os.getenv("COSMOS_REASON_URL")
        self.local_model_path = local_model_path
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        if self.inference_server:
            return True
        if COSMOS_AVAILABLE and self.local_model_path:
            return True
        # Check for local NIM container
        if os.path.exists("/tmp/cosmos_reason_available"):
            return True
        return False

    def is_available(self) -> bool:
        return self._available

    def analyze_clip(
        self,
        video_path: str,
        question: str = "Describe what is happening in this video clip.",
        num_frames: int = 8,
    ) -> dict[str, Any]:
        """Run Cosmos Reason 2 on a CCTV video clip.

        Args:
            video_path: Path to MP4 clip (e.g., 5-10 seconds).
            question: Prompt for causal reasoning.
            num_frames: Number of frames to sample from clip.

        Returns:
            Dict with reasoning, confidence, and suggested actions.
        """
        if not self._available:
            return {"status": "unavailable", "reasoning": "Cosmos Reason 2 not loaded."}

        # Extract frames from video
        frames = self._extract_frames(video_path, num_frames)
        if not frames:
            return {"status": "error", "reasoning": "Could not extract frames from video."}

        if self.inference_server:
            return self._call_nim(frames, question)
        elif COSMOS_AVAILABLE:
            return self._call_local(frames, question)
        else:
            return self._call_fallback(frames, question)

    def _extract_frames(self, video_path: str, num_frames: int) -> list[Path]:
        """Extract evenly spaced frames using ffmpeg."""
        out_dir = Path(tempfile.mkdtemp(prefix="cosmos_frames_"))
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"select='not(mod(n,{max(1, int(30/num_frames))}))',scale=512:512",
            "-frames:v", str(num_frames),
            str(out_dir / "frame_%03d.jpg"),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            return sorted(out_dir.glob("frame_*.jpg"))
        except Exception:
            return []

    def _call_nim(self, frames: list[Path], question: str) -> dict[str, Any]:
        """Call Cosmos Reason 2 NIM endpoint."""
        import base64
        import httpx

        image_b64 = []
        for fp in frames[:8]:
            with open(fp, "rb") as f:
                image_b64.append(base64.b64encode(f.read()).decode())

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        *[
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                            for b64 in image_b64
                        ],
                    ],
                }
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }

        try:
            resp = httpx.post(
                f"{self.inference_server}/v1/chat/completions",
                json=payload,
                timeout=60.0,
            )
            data = resp.json()
            reasoning = data["choices"][0]["message"]["content"]
            return {
                "status": "ok",
                "reasoning": reasoning,
                "model": self.model_name,
                "frames_analyzed": len(image_b64),
            }
        except Exception as exc:
            return {"status": "nim_error", "reasoning": str(exc)}

    def _call_local(self, frames: list[Path], question: str) -> dict[str, Any]:
        """Call local Cosmos Reason 2 model."""
        # Placeholder for local model inference
        # In production, use cosmos1.models.diffusion.nemo inference API
        return {
            "status": "local_stub",
            "reasoning": f"Local Cosmos Reason 2 analysis of {len(frames)} frames: {question}",
            "model": self.model_name,
        }

    def _call_fallback(self, frames: list[Path], question: str) -> dict[str, Any]:
        """Fallback: use Nemotron Omni on first frame only."""
        import base64
        import httpx

        if not frames:
            return {"status": "fallback_no_frames", "reasoning": "No frames available."}

        with open(frames[0], "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": "nvidia/nemotron-3-nano-omni",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"[VIDEO-CLIP-FIRST-FRAME] {question}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ],
            "max_tokens": 256,
        }

        try:
            resp = httpx.post(
                "http://localhost:8000/v1/chat/completions",
                json=payload,
                timeout=30.0,
            )
            data = resp.json()
            return {
                "status": "fallback_nemotron",
                "reasoning": data["choices"][0]["message"]["content"],
                "model": "nemotron-3-nano-omni",
                "note": "Cosmos Reason 2 unavailable; used Nemotron Omni on first frame.",
            }
        except Exception as exc:
            return {"status": "fallback_error", "reasoning": str(exc)}


# Singleton
_cosmos_client: CosmosReasonClient | None = None


def get_cosmos_client() -> CosmosReasonClient:
    global _cosmos_client
    if _cosmos_client is None:
        _cosmos_client = CosmosReasonClient()
    return _cosmos_client
