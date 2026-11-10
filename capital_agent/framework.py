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


def legacy_bank_calculation_allowed(ds: Dataset, profile: FrameworkProfile) -> bool:
    """Allow calculation-only processing for older bank maker workbooks."""
    if profile is not BANK_PROFILE:
        return False
    if not ds.capital_inputs or not ds.rwa_inputs:
        return False
    required = ("asset_class", "risk_weight", "asset_value_inr_lakhs")
    return all(
        all(rec.get(key) is not None for key in required)
        and isinstance(rec.get("risk_weight"), (int, float))
        and isinstance(rec.get("asset_value_inr_lakhs"), (int, float))
        and rec["risk_weight"] >= 0
        and rec["asset_value_inr_lakhs"] >= 0
        for rec in ds.rwa_inputs
    )


def legacy_bank_benchmark_allowed(ds: Dataset, profile: FrameworkProfile) -> bool:
    """Whether a legacy bank workbook also supplies an explicit benchmark."""
    return legacy_bank_calculation_allowed(ds, profile) and any(
        norm(rec.get("metric", "")) == "total rwa"
        and rec.get("expected_value") is not None
        for rec in ds.expected_output
    )


def supplemental_bank_risk_gaps(ds: Dataset, profile: FrameworkProfile) -> list[str]:
    if profile is not BANK_PROFILE:
        return []
    gaps = []
    if "market_inputs" not in ds.sheet_map:
        gaps.append(
            "Commercial-bank market-risk RWA schedule is missing; provide market-risk "
            "capital charge/RWA or an explicit 0 nil row."
        )
    if "operational_inputs" not in ds.sheet_map:
        gaps.append(
            "Commercial-bank operational-risk schedule is missing; provide operational-risk "
            "capital charge/RWA or an explicit 0 nil row."
        )
    return gaps


def preflight_diagnostics(ds: Dataset, profile: FrameworkProfile) -> list[str]:
    missing = [role for role in profile.required_roles if role not in ds.sheet_map]
    diagnostics = []
    if missing:
        diagnostics.append(
            f"{profile.framework} requires evidence schedule(s) not found: {', '.join(missing)}. "
            "Upload the named schedule or select the correct framework."
        )
    if profile is BANK_PROFILE:
        if "capital_inputs" in ds.sheet_map:
            rows = [r for r in ds.capital_inputs if str(r.get("capital_category", "")).strip()]
            if not rows:
                diagnostics.append(
                    "Commercial-bank capital composition schedule has no populated Capital_Category evidence. "
                    "Provide CET1/AT1/Tier 2 rows with source amounts and eligibility support."
                )
        if "rwa_inputs" in ds.sheet_map and not ds.rwa_inputs:
            diagnostics.append(
                "Commercial-bank RWA schedule contains no data rows. Provide credit-RWA exposures and risk weights."
            )
        if not legacy_bank_calculation_allowed(ds, profile):
            diagnostics.extend(supplemental_bank_risk_gaps(ds, profile))
    if profile is UNKNOWN_PROFILE:
        diagnostics.append(
            "Entity/framework could not be determined from explicit workbook markers or RBI schedule evidence. "
            "Add an Entity/Framework field or provide an RBI registration and capital schedule."
        )
    return diagnostics
