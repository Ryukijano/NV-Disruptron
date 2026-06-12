"""GPU-accelerated CCTV frame decode using NVIDIA DALI.

Replaces CPU PIL decode in live_feed_pipeline.py and detect_video_stream()
with GPU JPEG decode + resize via DALI. Benchmarkable CPU vs GPU.

Usage:
    from features.vision.dali_pipeline import DALICCTVDecoder
    decoder = DALICCTVDecoder(batch_size=1, target_size=(480, 640))
    pil_images = decoder.decode_batch([image_bytes_1, image_bytes_2])
"""

import io
import time
from typing import Any

import numpy as np
from PIL import Image

# DALI imports
from nvidia.dali import pipeline_def
import nvidia.dali.fn as fn
import nvidia.dali.types as types


def _bytes_to_dali_source(image_bytes_list: list[bytes]):
    """Convert raw JPEG bytes to DALI ExternalSource format."""
    arrays = []
    for b in image_bytes_list:
        arr = np.frombuffer(b, dtype=np.uint8)
        arrays.append(arr)
    return arrays


@pipeline_def(batch_size=1, num_threads=2, device_id=0)
def _jpeg_decode_pipeline(target_size=(480, 640)):
    """DALI pipeline: decode JPEG bytes → resize → output RGB GPU tensors."""
    jpegs = fn.external_source(dtype=types.UINT8, name="jpegs")
    images = fn.decoders.image(jpegs, device="mixed", output_type=types.RGB)
    resized = fn.resize(images, size=target_size, device="gpu")
    return resized


class DALICCTVDecoder:
    """GPU-accelerated decoder for CCTV JPEG frames."""

    def __init__(self, batch_size: int = 1, target_size: tuple[int, int] = (480, 640)):
        self.batch_size = batch_size
        self.target_size = target_size
        self.pipe = _jpeg_decode_pipeline(
            batch_size=batch_size,
            num_threads=2,
            device_id=0,
            target_size=target_size,
        )
        self.pipe.build()

    def decode_batch(self, image_bytes_list: list[bytes]) -> list[Image.Image]:
        """Decode a batch of JPEG bytes to PIL Images (GPU accelerated)."""
        if not image_bytes_list:
            return []

        # Pad to batch_size if needed
        padded = image_bytes_list + [image_bytes_list[-1]] * (
            self.batch_size - len(image_bytes_list)
        )

        dali_arrays = _bytes_to_dali_source(padded)
        self.pipe.feed_input("jpegs", dali_arrays)
        outputs = self.pipe.run()

        # Convert GPU tensor to CPU numpy → PIL
        gpu_tensor = outputs[0]
        cpu_array = np.array(gpu_tensor.as_cpu())

        pil_images = []
        for i in range(len(image_bytes_list)):
            arr = cpu_array[i]
            pil_images.append(Image.fromarray(arr))

        return pil_images

    def decode_single(self, image_bytes: bytes) -> Image.Image:
        """Decode a single JPEG image."""
        results = self.decode_batch([image_bytes])
        return results[0]

    def benchmark(self, image_bytes: bytes, n: int = 100) -> dict[str, float]:
        """Benchmark GPU decode vs CPU PIL decode."""
        import time

        # GPU warmup
        self.decode_single(image_bytes)
        self.decode_single(image_bytes)

        # GPU timing
        t0 = time.perf_counter()
        for _ in range(n):
            self.decode_single(image_bytes)
        gpu_time = (time.perf_counter() - t0) / n

        # CPU timing
        t0 = time.perf_counter()
        for _ in range(n):
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = img.resize(self.target_size)
        cpu_time = (time.perf_counter() - t0) / n

        return {
            "gpu_ms": round(gpu_time * 1000, 3),
            "cpu_ms": round(cpu_time * 1000, 3),
            "speedup": round(cpu_time / gpu_time, 2),
        }


# Singleton decoder instance
_decoder: DALICCTVDecoder | None = None


def get_decoder(batch_size: int = 1, target_size: tuple[int, int] = (480, 640)) -> DALICCTVDecoder:
    """Lazy singleton for DALICCTVDecoder."""
    global _decoder
    if _decoder is None:
        _decoder = DALICCTVDecoder(batch_size=batch_size, target_size=target_size)
    return _decoder


def dali_decode(image_bytes: bytes, target_size: tuple[int, int] = (480, 640)) -> Image.Image:
    """Convenience: decode single image via DALI."""
    decoder = get_decoder(batch_size=1, target_size=target_size)
    return decoder.decode_single(image_bytes)
