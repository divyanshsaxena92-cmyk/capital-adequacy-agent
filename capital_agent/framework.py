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
    exposure_keys = (
        "asset_value_inr_lakhs", "asset_value", "exposure",
        "gross_exposure", "outstanding_amount", "loan_amount", "balance",
        "amount", "amount_inr_lakhs", "exposure_inr_lakhs",
        "outstanding_inr_lakhs", "ead", "ead_inr_lakhs",
    )
    capital_valid = all(
        bool(str(rec.get("capital_category", "")).strip())
        and isinstance(rec.get("raw_amount_inr_lakhs"), (int, float))
        and not isinstance(rec.get("raw_amount_inr_lakhs"), bool)
        for rec in ds.capital_inputs
    )

    def valid_rwa_row(rec):
        if not bool(str(rec.get("asset_class", "")).strip()):
            return False
        rw = rec.get("risk_weight")
        if not isinstance(rw, (int, float)) or isinstance(rw, bool) or rw < 0:
            return False
        exposures = [rec.get(key) for key in exposure_keys if key in rec and rec.get(key) not in (None, "")]
        return bool(exposures) and all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
            for value in exposures
        )

    return all(
        valid_rwa_row(rec)
        for rec in ds.rwa_inputs
    ) and capital_valid


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
            headers = ", ".join(ds.recognized_headers.get("rwa_inputs", []))
            if ds.rwa_inputs and headers:
                diagnostics.append(
                    "Commercial-bank RWA schedule rows are incomplete or non-numeric for legacy calculation. "
                    f"Recognized headers: {headers}. Provide Asset_Class and numeric Risk_Weight; "
                    "provide one numeric exposure/value column (for example Asset_Value_INR_Lakhs, "
                    "Exposure, Outstanding_Amount, Balance, EAD, or another recognized numeric alias)."
                )
            diagnostics.extend(supplemental_bank_risk_gaps(ds, profile))
    if profile is UNKNOWN_PROFILE:
        diagnostics.append(
            "Entity/framework could not be determined from explicit workbook markers or RBI schedule evidence. "
            "Add an Entity/Framework field or provide an RBI registration and capital schedule."
        )
    return diagnostics
