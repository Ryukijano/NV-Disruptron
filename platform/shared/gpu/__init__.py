"""RAPIDS GPU acceleration layer for NV-Disruptron.

All modules expose GPU-accelerated paths with CPU fallbacks.
Import pattern:
    from platform.shared.gpu import GPU_AVAILABLE
    if GPU_AVAILABLE:
        import cudf
    else:
        import pandas as cudf
"""

from __future__ import annotations

import os

# Allow explicit override for testing CPU fallback paths
RAPIDS_DISABLED = os.getenv("RAPIDS_DISABLED", "").lower() in ("1", "true", "yes")

GPU_AVAILABLE = False
GPU_LIBS: dict[str, Any] = {}

if not RAPIDS_DISABLED:
    try:
        import cudf
        import cuspatial
        GPU_LIBS["cudf"] = cudf
        GPU_LIBS["cuspatial"] = cuspatial
        GPU_AVAILABLE = True
    except ImportError:
        pass

try:
    import cugraph
    if not RAPIDS_DISABLED:
        GPU_LIBS["cugraph"] = cugraph
        GPU_AVAILABLE = True
except ImportError:
    pass

try:
    import cuml
    if not RAPIDS_DISABLED:
        GPU_LIBS["cuml"] = cuml
        GPU_AVAILABLE = True
except ImportError:
    pass

try:
    import cuvs
    if not RAPIDS_DISABLED:
        GPU_LIBS["cuvs"] = cuvs
        GPU_AVAILABLE = True
except ImportError:
    pass

try:
    import cudss
    if not RAPIDS_DISABLED:
        GPU_LIBS["cudss"] = cudss
        GPU_AVAILABLE = True
except ImportError:
    pass

# Degrade to CPU-only if any forced-disable or partial load
if RAPIDS_DISABLED:
    GPU_AVAILABLE = False

from typing import Any

__all__ = ["GPU_AVAILABLE", "GPU_LIBS", "RAPIDS_DISABLED"]
