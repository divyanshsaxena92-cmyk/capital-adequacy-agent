"""Context object handed to every tab's render(ctx)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Ctx:
    st: object                 # the streamlit module
    run: object | None         # capital_agent.agent.Run (None before first run)
    base_dir: str
    input_path: str | None
    rerun: callable = None     # rerun(decisions_rows: list[dict]) -> re-executes the agent with SME decisions
    extra: dict = field(default_factory=dict)

    def fmt_lakhs(self, v) -> str:
        return "-" if v is None else f"₹{v:,.2f} L"
