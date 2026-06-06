"""Shared London ward / IMD / GVA data access for NV-Disruptron MCP servers."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # platform/shared → repo root
DATA = ROOT / "data"
IMD_CSV = DATA / "london_wards_imd.csv"
GVA_CSV = DATA / "borough_gva_per_job.csv"

# TfL disruption severity weights for impact scoring.
SEVERITY_WEIGHTS = {
    "good service": 0.0,
    "minor delays": 0.25,
    "severe delays": 0.75,
    "part suspended": 0.85,
    "part closure": 0.9,
    "suspended": 1.0,
    "closed": 1.0,
    "reduced service": 0.5,
    "step free access closed": 0.15,
    "planned closure": 0.4,
    "planned": 0.35,
}


@dataclass(frozen=True)
class WardRecord:
    ward_code: str
    ward_name: str
    borough: str
    population: int
    working_age_population: int
    imd_extent_pct: float
    imd_extent_rank: int
    imd_average_rank: float
    imd_average_rank_rank: int

    @property
    def deprivation_quintile(self) -> int:
        """1 = most deprived, 5 = least deprived (London ward quintiles)."""
        rank = self.imd_average_rank_rank
        if rank <= 130:
            return 1
        if rank <= 260:
            return 2
        if rank <= 390:
            return 3
        if rank <= 520:
            return 4
        return 5


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def load_wards() -> list[WardRecord]:
    if not IMD_CSV.exists():
        raise FileNotFoundError(
            f"{IMD_CSV} not found. Run: uv run python scripts/prepare_data.py"
        )

    wards: list[WardRecord] = []
    with IMD_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wards.append(
                WardRecord(
                    ward_code=row["Ward Code"].strip(),
                    ward_name=row["Ward Name"].strip(),
                    borough=row["Borough"].strip(),
                    population=_to_int(row.get("Population")),
                    working_age_population=_to_int(row.get("Working age population")),
                    imd_extent_pct=_to_float(row.get("IMD Extent %")),
                    imd_extent_rank=_to_int(row.get("IMD Extent Rank")),
                    imd_average_rank=_to_float(row.get("IMD Average rank")),
                    imd_average_rank_rank=_to_int(row.get("IMD average rank rank")),
                )
            )
    return wards


@lru_cache(maxsize=1)
def load_gva_by_borough() -> dict[str, float]:
    if not GVA_CSV.exists():
        return {}
    out: dict[str, float] = {}
    with GVA_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["borough"].strip().lower()] = _to_float(row.get("gva_per_job_gbp_k"))
    return out


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def find_ward(query: str) -> WardRecord | None:
    q = normalize(query)
    wards = load_wards()
    for ward in wards:
        if q in {normalize(ward.ward_code), normalize(ward.ward_name)}:
            return ward
    for ward in wards:
        if q in normalize(ward.ward_name) or q in normalize(ward.borough):
            if q == normalize(ward.ward_name):
                return ward
    # Fuzzy: ward name contains query
    matches = [w for w in wards if q in normalize(w.ward_name)]
    return matches[0] if len(matches) == 1 else None


def search_wards(query: str, limit: int = 10) -> list[WardRecord]:
    q = normalize(query)
    if not q:
        return []
    wards = load_wards()
    scored: list[tuple[int, WardRecord]] = []
    for ward in wards:
        name = normalize(ward.ward_name)
        borough = normalize(ward.borough)
        code = normalize(ward.ward_code)
        score = 0
        if q == name or q == code:
            score = 100
        elif name.startswith(q):
            score = 80
        elif q in name:
            score = 60
        elif q in borough:
            score = 40
        if score:
            scored.append((score, ward))
    scored.sort(key=lambda x: (-x[0], x[1].imd_average_rank_rank))
    return [w for _, w in scored[:limit]]


def wards_by_borough(borough: str) -> list[WardRecord]:
    q = normalize(borough)
    return [w for w in load_wards() if q in normalize(w.borough)]


def rank_wards_by_deprivation(limit: int = 20, borough: str | None = None) -> list[WardRecord]:
    wards = wards_by_borough(borough) if borough else load_wards()
    wards = sorted(wards, key=lambda w: w.imd_average_rank_rank)
    return wards[: max(1, min(limit, len(wards)))]


def ward_to_dict(ward: WardRecord) -> dict:
    gva = load_gva_by_borough().get(normalize(ward.borough), 55.0)
    return {
        "ward_code": ward.ward_code,
        "ward_name": ward.ward_name,
        "borough": ward.borough,
        "population": ward.population,
        "working_age_population": ward.working_age_population,
        "imd_extent_pct": round(ward.imd_extent_pct, 4),
        "imd_extent_rank": ward.imd_extent_rank,
        "imd_average_rank": round(ward.imd_average_rank, 2),
        "imd_deprivation_rank": ward.imd_average_rank_rank,
        "deprivation_quintile": ward.deprivation_quintile,
        "gva_per_job_gbp_k": gva,
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def infer_severity_weight(status_text: str, closure_text: str = "") -> float:
    text = normalize(f"{status_text} {closure_text}")
    for key, weight in SEVERITY_WEIGHTS.items():
        if key in text:
            return weight
    return 0.5 if text else 0.0


def compute_impact_score(
    ward: WardRecord,
    severity: float,
    commuters_affected: int | None = None,
) -> dict:
    """Composite vulnerability × severity × population-normalized impact."""
    pop = commuters_affected if commuters_affected is not None else ward.working_age_population
    gva = load_gva_by_borough().get(normalize(ward.borough), 55.0)
    deprivation_factor = 1.0 + (6 - ward.deprivation_quintile) * 0.15
    vulnerability = ward.imd_extent_pct * deprivation_factor
    impact_index = round(vulnerability * severity * 100, 2)
    # Rough hourly economic exposure (£000s GVA) for affected working-age residents
    economic_gbp_k_per_hour = round(pop * severity * (gva / 2000), 2)
    return {
        **ward_to_dict(ward),
        "severity_weight": round(severity, 3),
        "vulnerability_score": round(vulnerability, 4),
        "impact_index": impact_index,
        "commuters_estimated": pop,
        "economic_exposure_gbp_k_per_hour": economic_gbp_k_per_hour,
    }
