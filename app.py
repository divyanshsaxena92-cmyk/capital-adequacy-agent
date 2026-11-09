"""Capital Adequacy Agent - Streamlit front end (offline: no LLM, no API key, no data leaves the machine).

    python -m streamlit run app.py

Pages are plug-ins in ui/tabs/ (see ui/registry.py). The sidebar holds navigation, the client
workbook upload and the run button.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import traceback

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from capital_agent.agent import Run  # noqa: E402
from capital_agent.bigdata import DataStore  # noqa: E402
from capital_agent.rag_store import RagStore  # noqa: E402
from capital_agent.report import build_pack  # noqa: E402
from capital_agent.security import deployment_safety_check  # noqa: E402
from ui import preflight, registry, theme  # noqa: E402
from ui.context import Ctx  # noqa: E402

SAMPLE = os.path.join(HERE, "data", "sample_client_001.xlsx")
STORE = os.environ.get("CAPITAL_AGENT_STORE", os.path.join(HERE, "store"))
RAG_DB = os.path.join(STORE, "rag.sqlite")
DATA_DB = os.path.join(STORE, "data.sqlite")
SOURCES = os.path.join(HERE, "regulatory_kb", "sources.yaml")
LIBRARY = os.path.join(HERE, "regulatory_kb", "library")
CURATED = os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json")
TMP = os.path.join(tempfile.gettempdir(), "capital_agent_ui")
os.makedirs(TMP, exist_ok=True)
DEPLOYMENT = deployment_safety_check()

st.set_page_config(page_title="Capital Adequacy Agent", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")
theme.inject(st)

ss = st.session_state
for k, v in {"run": None, "input_path": None, "preflight": None, "config": {}, "error": None,
             "decisions": [], "loan_tape": None, "chat": []}.items():
    ss.setdefault(k, v)


# ------------------------------------------------------------------ stores (local SQLite)
def _stores():
    if "rag_store" not in ss or ss.rag_store.path != RAG_DB:
        ss.rag_store = RagStore(RAG_DB)
        ss.rag_store.seed_curated(CURATED)          # knowledge base is never empty
        ss.library_result = ss.rag_store.ingest_folder(LIBRARY)   # any RBI PDFs dropped in the library folder
    if "data_store" not in ss or ss.data_store.path != DATA_DB:
        ss.data_store = DataStore(DATA_DB)
    return ss.rag_store, ss.data_store


rag_store, data_store = _stores()


def _save_upload(upload, suffix) -> str:
    data = upload.getvalue()
    path = os.path.join(TMP, hashlib.sha1(data).hexdigest()[:12] + suffix)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(data)
    return path


def execute(input_path: str, cfg: dict, decisions: list[dict] | None = None):
    dpath = None
    if decisions:
        dpath = os.path.join(TMP, "decisions_ui.csv")
        with open(dpath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["exception_id", "decision", "reviewer", "comment"])
            w.writeheader()
            w.writerows(decisions)
    try:
        ss.run = Run(input_path, HERE, "rules", cfg["layer"], dpath, cfg["threshold"],
                     rag_db=RAG_DB, loan_tape=ss.loan_tape).execute()
        ss.error = None
        import datetime as _dt
        ss.setdefault("history", [])
        ss.history = (ss.history + [{"time": _dt.datetime.now().strftime("%H:%M:%S"), "run_id": ss.run.run_id,
                                     "crar": ss.run.final.crar, "tier1": ss.run.final.tier1, "rwa": ss.run.final.total_rwa,
                                     "decisions": len(decisions or []),
                                     "open": sum(e.status == "OPEN" for e in ss.run.exceptions)}])[-12:]
        ss.decisions = decisions or []
    except Exception:
        ss.run, ss.error = None, traceback.format_exc()


def rerun_with_decisions(rows: list[dict]):
    merged = {d["exception_id"]: d for d in ss.decisions}
    merged.update({d["exception_id"]: d for d in rows})
    execute(ss.input_path, ss.config, list(merged.values()))
    st.toast(f"Applied {len(rows)} decision(s) and re-ran the agent" if rows else "Re-ran the agent")
    st.rerun()


def set_loan_tape(summary: dict | None):
    ss.loan_tape = summary
    if ss.input_path and ss.config:
        execute(ss.input_path, ss.config, ss.decisions or None)
    st.toast("Loan tape attached to the agent run" if summary else "Loan tape detached")
    st.rerun()


# ------------------------------------------------------------------ sidebar controls
with st.sidebar:
    st.markdown('<div class="gt-side-prod">Capital Adequacy Agent</div>'
                '<div class="gt-side-sub">Tier 1 · Tier 2 · RWA · CRAR under RBI prudential norms</div>',
                unsafe_allow_html=True)
    from ui import access
    if access.is_admin(st) and DEPLOYMENT["client_uploads_allowed"]:
        upload = st.file_uploader("Client workbook (.xlsx)", type=["xlsx", "xlsm"])
    else:
        upload = None
        st.caption("View-only: showing synthetic fixtures. Client workbook uploads are disabled on Community Cloud.")
    input_path = _save_upload(upload, ".xlsx") if upload else SAMPLE
    st.caption(f"Using: **{upload.name if upload else 'sample client (CLIENT_001)'}**")
    with st.expander("Agent settings"):
        layer = st.selectbox("NBFC layer", ["ML", "UL"], help="Middle / Upper layer under scale-based regulation")
        threshold = st.slider("Auto-accept confidence", 0.50, 0.99, 0.80, 0.01,
                              help="Below this, a classification goes to human review")
    go = st.button("Run agent", type="primary", width="stretch")
    st.markdown('<div class="gt-offline">Offline — no LLM, no API key. Client data stays on this machine.</div>',
                unsafe_allow_html=True)
access.admin_panel(st)
cfg = {"layer": layer, "threshold": threshold}

# ------------------------------------------------------------------ preflight + run
if input_path != ss.input_path:
    ss.preflight, ss.run, ss.decisions, ss.error, ss.chat = None, None, [], None, []
    try:
        ss.preflight = preflight.run(input_path)
    except Exception:
        ss.error = traceback.format_exc()
    ss.input_path = input_path
pf = ss.preflight
if (go or (ss.run is None and input_path == SAMPLE and not ss.error)) and pf and not pf["blocking"]:
    ss.config = cfg
    with st.spinner("Running: ingest → validate → classify → calculate → review queue"):
        execute(input_path, cfg)
run = ss.run

# downloads
if run:
    with st.sidebar:
        with st.expander("Downloads", expanded=False):
            out = os.path.join(TMP, f"pack_{run.run_id}.xlsx")
            if not os.path.exists(out):
                build_pack(run, out)
            with open(out, "rb") as f:
                st.download_button("Excel output pack", f.read(),
                                   file_name=f"Capital_Agent_Output_{run.ds.reporting_date}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   width="stretch")
            from capital_agent import ledger as _ledger, memo as _memo
            st.download_button("Calculation ledger (CSV)", _ledger.to_csv(run),
                               file_name=f"Calculation_ledger_{run.ds.reporting_date}.csv", mime="text/csv", width="stretch")
            st.download_button("Management memo (HTML → PDF)", _memo.build(run, rag_store),
                               file_name=f"Capital_adequacy_memo_{run.ds.reporting_date}.html", mime="text/html", width="stretch")
            st.download_button("Run record (JSON)", json.dumps(run.to_json(), indent=2, default=str).encode(),
                               file_name=f"{run.run_id}.json", mime="application/json", width="stretch")
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["exception_id", "severity", "title", "decision", "reviewer", "comment"])
            for e in run.exceptions:
                w.writerow([e.exc_id, e.severity, e.title, e.decision, e.reviewer, e.comment])
            st.download_button("Decisions (CSV)", buf.getvalue().encode(), file_name="decisions.csv",
                               mime="text/csv", width="stretch")
            with open(SAMPLE, "rb") as f:
                st.download_button("Input template", f.read(), file_name="input_template_sample.xlsx",
                                   width="stretch")

with st.sidebar:
    st.markdown('<div class="gt-foot">Grant Thornton Bharat · internal prototype<br>'
                'Decision support only — figures require reviewer sign-off.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ pages
ctx = Ctx(st=st, run=run, base_dir=HERE, input_path=ss.input_path, rerun=rerun_with_decisions,
          extra={"preflight": pf, "rag": rag_store, "data": data_store, "sources_path": SOURCES,
                 "library": LIBRARY, "set_loan_tape": set_loan_tape, "save_upload": _save_upload,
                 "loan_tape": ss.loan_tape})


def _page_fn(tab):
    def _render():
        if not tab.get("bare"):
            theme.page(st, tab["title"], tab.get("subtitle", ""))
        if tab["needs_run"] and run is None:
            theme.note(st, "Run the agent from the sidebar to see this page.")
            return
        try:
            tab["render"](ctx)
        except Exception:  # one broken page never takes down the app
            st.error(f"This page ({tab['module']}.py) failed to render.")
            st.code(traceback.format_exc())
    _render.__name__ = f"page_{tab['module']}"
    return _render


tabs = registry.discover()
pages = {t["module"]: st.Page(_page_fn(t), title=t["title"], icon=t["icon"], url_path=t["module"].split("_", 1)[-1],
                              default=(t["module"] == tabs[0]["module"])) for t in tabs}
ctx.extra["pages"] = pages
ctx.extra["commands"] = [{"label": t["title"], "page": t["module"], "section": t["section"]} for t in tabs]
nav = {sec: [pages[t["module"]] for t in items] for sec, items in registry.grouped(tabs).items()}
current = st.navigation(nav)
# ------------------------------------------------------------------ header band (the Overview has its own top bar)
_bare = {t["title"] for t in tabs if t.get("bare")}
if getattr(current, "title", "") not in _bare or run is None:   # component pages carry their own command bar
    if run:
        open_hi = sum(e.status == "OPEN" and e.severity in ("Critical", "High") for e in run.exceptions)
        chips = [(f"As at {run.ds.reporting_date:%d %b %Y}", ""),
                 (f"{run.entity_type} · {'Middle' if run.layer == 'ML' else 'Upper'} Layer", ""),
                 ("Draft — review pending" if run.status.startswith("DRAFT") else "Ready for checker",
                  "warn" if run.status.startswith("DRAFT") else "ok")]
        if open_hi:
            chips.append((f"{open_hi} high-priority items", "bad"))
        chips.append(("Offline", "ok"))
    else:
        chips = [("No run yet", "warn"), ("Offline", "ok")]
    theme.band(st, "Capital Adequacy Agent",
               "Tier 1 and Tier 2 capital, risk-weighted assets and CRAR under RBI prudential norms", chips)

if pf and pf["blocking"]:
    st.error("This workbook can't be processed yet:\n\n" + "\n".join(f"- {b}" for b in pf["blocking"]))
if pf and pf.get("warnings"):
    st.warning("Calculated draft only — management-ready status remains blocked:\n\n" +
               "\n".join(f"- {w}" for w in pf["warnings"]))
if ss.error:
    st.error("The agent stopped with an error. The Source workbook page shows how the file was read.")
    with st.expander("Error details"):
        st.code(ss.error)

current.run()
