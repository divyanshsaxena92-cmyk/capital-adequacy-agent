"""Local-only data boundary for client workbooks.

The production workflow is deliberately rules-only.  RBI source refreshes are
the only network operation and are never given workbook-derived values.
"""
from __future__ import annotations

import os

LOCAL_ONLY_POLICY = "LOCAL_ONLY_NO_CLIENT_DATA_TO_LLM_OR_NETWORK"


def deployment_safety_check() -> dict:
    """Enforce the deployment boundary before Streamlit creates upload controls."""
    deployment = str(os.environ.get("CAPITAL_AGENT_DEPLOYMENT", "")).strip().lower()
    cloud_hint = " ".join(str(os.environ.get(k, "")).lower() for k in (
        "STREAMLIT_SHARING_MODE", "STREAMLIT_RUNTIME_ENVIRONMENT", "ST_CLOUD"))
    community = deployment in {"community", "community_cloud", "streamlit_cloud"} or "community" in cloud_hint
    mode = str(os.environ.get("CAPITAL_AGENT_MODE", "full")).strip().lower()
    if community and mode != "viewer":
        raise RuntimeError(
            "Community Cloud is viewer-only for synthetic demonstrations. Set CAPITAL_AGENT_MODE=viewer "
            "and do not upload real client data; use an approved internal deployment for client work."
        )
    return {"deployment": deployment or "local/internal", "community_cloud": community,
            "client_uploads_allowed": not community}


def enforce_local_only(mode: str, llm_client=None) -> None:
    """Reject configurations that could send client data outside the process."""
    if mode != "rules" or llm_client is not None:
        raise ValueError(
            "Client-data boundary violation: Run accepts only mode='rules' and no "
            "LLM client. Use the offline deterministic workflow; RBI refreshes "
            "operate on public regulatory sources only."
        )
