"""Stage 4 - Deterministic calculation engine.

Pure arithmetic on classified inputs. Same inputs -> same outputs, always.
No LLM is involved anywhere in this module.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

LAKH = 100_000.0


# ----------------------------------------------------------------------------- CEM
@dataclass
class DealExposure:
    item_id: str
    deal_id: str
    contract_type: str          # "fx_gold" | "interest_rate"
    notional_inr: float
    notional_lakhs: float
    residual_years: float
    add_on: float
    pfe_lakhs: float
    source_ref: str


@dataclass
class CEMResult:
    deals: list
    replacement_cost: float
    rc_source_ref: str
    pfe_total: float
    credit_equivalent: float
    counterparty_rw: float
    rwa_rc: float
    rwa_pfe: float

    @property
    def rwa(self) -> float:
        return self.rwa_rc + self.rwa_pfe


def add_on_factor(table: dict, contract_type: str, residual_years: float) -> float:
    for max_years, factor in table[contract_type]:
        if residual_years <= max_years:
            return factor
    return table[contract_type][-1][1]


def classify_contract(rec: dict) -> str:
    """Two different currencies => exchange-rate contract (incl. cross-currency swaps), para 18(7)(iii)(b)."""
    if rec.get("pay_ccy") and rec.get("receive_ccy") and rec["pay_ccy"] != rec["receive_ccy"]:
        return "fx_gold"
    return "interest_rate"


def compute_cem(deals: list[dict], reporting_date: dt.date, add_on_table: dict,
                replacement_cost: float, rc_ref: str, counterparty_rw: float) -> CEMResult:
    out = []
    for d in deals:
        ctype = classify_contract(d)
        notional_inr = float(d["pay_notional"]) if d.get("pay_ccy") == "INR" else float(d["receive_notional"])
        resid = (d["maturity_date"] - reporting_date).days / 365.0
        f = add_on_factor(add_on_table, ctype, resid)
        nl = notional_inr / LAKH
        out.append(DealExposure(d["item_id"], d["deal_id_masked"], ctype, notional_inr, nl, resid, f, nl * f,
                                f"'{d['_sheet']}'!{d['_cells'].get('pay_notional')}"))
    pfe = sum(x.pfe_lakhs for x in out)
    rc = max(replacement_cost, 0.0)
    return CEMResult(out, rc, rc_ref, pfe, rc + pfe, counterparty_rw, rc * counterparty_rw, pfe * counterparty_rw)


# ------------------------------------------------------------------------ capital
@dataclass
class CapitalLine:
    item_id: str
    label: str
    amount: float
    treatment: str              # T1_INCLUDE | T1_EXCLUDE | T1_DEDUCT | T2_INCLUDE | T2_GENERAL_PROVISION
    source_ref: str = ""

    @property
    def sign(self) -> int:
        return {"T1_INCLUDE": 1, "T1_DEDUCT": -1}.get(self.treatment, 0)

    @property
    def tier1_effect(self) -> float:
        if self.treatment == "T1_DEDUCT":
            return -abs(self.amount)
        if self.treatment == "T1_INCLUDE":
            return self.amount
        return 0.0


@dataclass
class RWALine:
    item_id: str
    label: str
    exposure: float
    risk_weight: float
    source_ref: str = ""

    @property
    def rwa(self) -> float:
        return self.exposure * self.risk_weight


@dataclass
class CapitalResult:
    tier1: float
    gp_gross: float
    gp_cap: float
    tier2_gp_eligible: float
    tier2: float
    rwa_credit_on_bs: float
    rwa_ccr: float
    total_rwa: float
    crar: float
    tier1_ratio: float
    tier2_limited_by_tier1: bool
    minimums: dict
    breaches: list = field(default_factory=list)
    tier2_other: float = 0.0

    def as_dict(self) -> dict:
        return {"Tier 1 Capital": self.tier1, "Tier 2 Capital": self.tier2, "Total RWA": self.total_rwa,
                "CRAR": self.crar, "Tier 1 Ratio": self.tier1_ratio}


def compute_capital(capital_lines: list[CapitalLine], rwa_lines: list[RWALine], cem: CEMResult,
                    gp_cap_rate: float, minimums: dict) -> CapitalResult:
    tier1 = sum(l.tier1_effect for l in capital_lines)
    gp_gross = sum(abs(l.amount) for l in capital_lines if l.treatment == "T2_GENERAL_PROVISION")
    tier2_other = sum(abs(l.amount) for l in capital_lines if l.treatment == "T2_INCLUDE")
    rwa_bs = sum(l.rwa for l in rwa_lines)
    total_rwa = rwa_bs + cem.rwa
    gp_cap = gp_cap_rate * total_rwa                      # para 13(iii)
    gp_elig = min(gp_gross, gp_cap)
    tier2 = min(gp_elig + tier2_other, max(tier1, 0.0))  # para 6(3): Tier 2 <= 100% of Tier 1
    crar = (tier1 + tier2) / total_rwa if total_rwa else 0.0
    t1r = tier1 / total_rwa if total_rwa else 0.0
    breaches = []
    if crar < minimums.get("crar", 0):
        breaches.append(f"CRAR {crar:.2%} below minimum {minimums['crar']:.0%}")
    if t1r < minimums.get("tier1", 0):
        breaches.append(f"Tier 1 ratio {t1r:.2%} below minimum {minimums['tier1']:.0%}")
    if "cet1" in minimums and t1r < minimums["cet1"]:
        breaches.append(f"CET1 ratio below minimum {minimums['cet1']:.0%}")
    return CapitalResult(tier1, gp_gross, gp_cap, gp_elig, tier2, rwa_bs, cem.rwa, total_rwa, crar, t1r,
                         gp_elig + tier2_other > max(tier1, 0.0), minimums, breaches, tier2_other)
