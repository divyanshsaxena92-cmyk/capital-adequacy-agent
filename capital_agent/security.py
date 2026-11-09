"""Local-only data boundary for client workbooks.

The production workflow is deliberately rules-only.  RBI source refreshes are
the only network operation and are never given workbook-derived values.
"""
from __future__ import annotations


LOCAL_ONLY_POLICY = "LOCAL_ONLY_NO_CLIENT_DATA_TO_LLM_OR_NETWORK"


def enforce_local_only(mode: str, llm_client=None) -> None:
    """Reject configurations that could send client data outside the process."""
    if mode != "rules" or llm_client is not None:
        raise ValueError(
            "Client-data boundary violation: Run accepts only mode='rules' and no "
            "LLM client. Use the offline deterministic workflow; RBI refreshes "
            "operate on public regulatory sources only."
        )
