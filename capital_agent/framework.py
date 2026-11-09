"""Entity and RBI-framework profiling for workbook preflight and runs."""
from __future__ import annotations

from dataclasses import dataclass

from .ingest import Dataset, norm


@dataclass(frozen=True)
class FrameworkProfile:
    entity_type: str
    framework: str
    minimums: dict
    required_roles: tuple[str, ...]
    required_evidence: tuple[str, ...]


NBFC_PROFILE = FrameworkProfile(
    "NBFC", "NBFC-CA-2025", {"crar": 0.15, "tier1": 0.10},
    ("balance_sheet",), ("RBI layer (ML/UL)", "owned-fund / Tier 1 composition"),
)
BANK_PROFILE = FrameworkProfile(
    "BANK", "SCB-CA-2025", {"crar": 0.115, "tier1": 0.095, "cet1": 0.055},
    ("balance_sheet", "capital_inputs", "rwa_inputs"),
    ("CET1/AT1/Tier 2 eligibility", "credit RWA", "market-risk RWA", "operational-risk RWA"),
)
UNKNOWN_PROFILE = FrameworkProfile(
    "UNKNOWN", "UNRESOLVED", {}, ("balance_sheet",),
    ("legal entity / RBI registration", "applicable RBI capital framework"),
)


def profile_for_dataset(ds: Dataset) -> FrameworkProfile:
    """Use explicit workbook markers first, then conservative schedule evidence."""
    text = norm(" ".join([
        ds.raw_text,
        " ".join(" ".join(v for v in headers) for headers in ds.recognized_headers.values()),
        " ".join(ds.sheet_map.values()),
    ]))
    if any(token in text for token in (
        "nbfc", "45-ic", "non-banking financial", "owned fund", "nbfc-ml", "nbfc-ul",
    )):
        return NBFC_PROFILE
    if any(token in text for token in (
        "commercial bank", "banking regulation act", "cet1", "at1", "basel iii",
        "market risk", "operational risk", "crar",
    )):
        return BANK_PROFILE
    return UNKNOWN_PROFILE


def preflight_diagnostics(ds: Dataset, profile: FrameworkProfile) -> list[str]:
    missing = [role for role in profile.required_roles if role not in ds.sheet_map]
    diagnostics = []
    if missing:
        diagnostics.append(
            f"{profile.framework} requires evidence schedule(s) not found: {', '.join(missing)}. "
            "Upload the named schedule or select the correct framework."
        )
    if profile is BANK_PROFILE:
        if "market_inputs" not in ds.sheet_map:
            diagnostics.append(
                "Commercial-bank market-risk RWA schedule is missing; total RWA cannot be signed off. "
                "Provide market-risk capital charge/RWA by reporting date, or explicitly document nil exposure."
            )
        if "operational_inputs" not in ds.sheet_map:
            diagnostics.append(
                "Commercial-bank operational-risk schedule is missing; total RWA cannot be signed off. "
                "Provide the applicable operational-risk capital charge/RWA, or explicitly document nil exposure."
            )
    if profile is UNKNOWN_PROFILE:
        diagnostics.append(
            "Entity/framework could not be determined from explicit workbook markers or RBI schedule evidence. "
            "Add an Entity/Framework field or provide an RBI registration and capital schedule."
        )
    return diagnostics
