"""Resolve NV-Disruptron repository root from any package location."""

from __future__ import annotations

from pathlib import Path

_MARKER = Path("data") / "london_wards_imd.csv"


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    for candidate in (p, *p.parents):
        if (candidate / _MARKER).is_file():
            return candidate
    raise RuntimeError(f"NV-Disruptron repo root not found from {p}")


REPO_ROOT = repo_root()
