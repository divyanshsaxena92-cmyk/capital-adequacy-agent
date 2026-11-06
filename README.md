# Capital Adequacy Agent (v1.4 — offline)

Computes Tier 1 / Tier 2 capital, risk-weighted assets and CRAR for an RBI-regulated entity, classifies every
balance-sheet item under RBI's norms with a paragraph citation, and sends every judgement call to a human.

**Runs fully offline. No LLM, no API key; client data never leaves the machine.**

## Run it

```bash
pip install -r requirements.txt
python -m streamlit run app.py          # opens http://localhost:8501
```

The sample client runs automatically. Upload a client workbook in the sidebar and click **Run agent**.

## How it works without an LLM

| Layer | What it does |
|---|---|
| **RAG knowledge base** (`capital_agent/rag_store.py`) | RBI's own text, split into numbered paragraphs (e.g. `7(iv)`), indexed with SQLite full-text search (BM25). Versioned by date, so a 31-Mar-2026 run only sees text in force then. |
| **Rules engine** (`rules/rule_library_v1.0.yaml`, `classifier.py`) | Maps each line item to an approved rule with an RBI citation and a confidence score. Ambiguous rules always go to human review. |
| **Calculation engine** (`engine.py`) | Deterministic Tier 1, Tier 2 cap, RWA, derivatives (CEM), ratios. Ties exactly to the sample benchmark. |
| **Assistant** (`assistant.py`) | Answers questions from the run's results and quotes RBI paragraphs. Nothing is generated, so nothing can be invented. |

### Loading RBI's text

Three routes, all on the **RBI library** page:

1. **Download & index from RBI** — fetches the official PDFs (needs internet).
2. **Library folder** — save RBI PDFs from your browser into `regulatory_kb/library/`. They're indexed on startup. Use this if RBI's site blocks automated downloads.
3. **Upload** a single PDF.

Curated summaries of the key paragraphs are pre-loaded, so search and the assistant work before any download.

## Pages

| Section | Pages |
|---|---|
| Dashboard | **Overview** — bento dashboard: isometric capital-vs-requirement view, compliance, CRAR sensitivity, capital bridge, review queue, RWA mix · **Ask the Agent** |
| Capital | Tier 1 · Tier 2 · Risk-weighted assets · Derivatives (CEM) |
| Review | **Exception queue** (signed SME decisions, re-run) · **What-if simulator** · Sensitivity |
| Regulation | RBI library · Rules in force · Agent reasoning |
| Data & evidence | Large data import (loan tapes) · Validation · Audit trail · Source workbook |

**Ask the Agent** handles: ratios and compliance, why an item was flagged, why an item was treated a certain way,
risk-weight lookups, failed data checks, what-ifs (*"what if loans are at 100%?"*), and any RBI question.

**What-if simulator** lets a reviewer toggle each judgement call or change the loan risk weight and see CRAR move.
Reported figures change only through a signed decision in the Exception queue.

## Security notes for review

- No outbound calls except optional downloads of RBI's public PDFs.
- Streamlit usage statistics are disabled (`.streamlit/config.toml`).
- Uploaded files and the knowledge base live in local SQLite files under `store/`.
- Source workbooks are never modified; outputs go to a separate Excel pack.

## Command line and tests

```bash
python run_agent.py --input data/sample_client_001.xlsx [--loan-tape tape.xlsx]
python -m capital_agent.rag_store search "statutory reserve" --as-of 2026-03-31
python -m unittest discover -s tests -v          # 63 tests
```

Pages are plug-ins: copy `ui/tabs/_template.py` to add one.


The Overview is plain HTML/CSS/SVG generated in `ui/overview_v3.py` (fintech layout: top bar, capital hero, component cards, ratio chart with tooltip, review table, validation score; the earlier `overview_v2.py` variant is kept) (no JavaScript, no external assets): gradient hero with count-up figures and ratio rings, gradient KPI tiles, a dark "judgement calls at stake" tile, animated bridge/donut/sensitivity charts, a floating 3D capital view and an agent-activity timeline. All motion is CSS and switches off under the OS reduce-motion setting.

### Note on the Overview rendering (v0.9 fix)
Streamlit sanitises `st.html` content with DOMPurify, which silently drops a `<style>` block placed first and any
`<style>` block containing `<`. All dashboard HTML therefore goes through `ui/htmlsafe.prepare()`, which merges the
styles into one block, escapes `<` as `\3C`, and wraps everything in a `<div>`. A regression test enforces this.

## v1.0 — Capital Command Centre (Overview)

The Overview is now a local Streamlit **custom component** (`ui/dashboard_component/index.html` + `ui/command_center.py`).
It runs in its own frame, so no HTML sanitiser alters it, and it is interactive:

- **Command bar** — live search across every panel (Enter sends the question to *Ask the Agent*; Ctrl+K focuses it),
  day/night theme, live clock, alerts bell with the high-priority items.
- **Hero + run status** — CRAR with ratio rings, compliance badges; checks ring, benchmark tie-out, rule/KB versions.
- **KPI tiles**, **3D capital-vs-requirement view**, **judgement calls at stake**.
- **Capital analytics** — tabs for the bridge, RWA mix and a components table.
- **Live what-if** — drag the loan risk weight; CRAR, Tier 1, headroom and compliance update instantly
  (values pre-computed by the engine for every 5% step).
- **Review queue** — filters, sort by impact, click a row to open the exception queue.
- **Risk heat map**, **agent activity**, **data quality**, **RBI paragraphs**, **status footer**.

Security: the component's JavaScript is local, makes no network requests (a test enforces this) and loads no
external libraries. Clicks and searches come back to Python only as small JSON messages.

## v1.1 — The RBI "brain": how regulations get in and stay current

**Three ways RBI text gets in** (RBI library page):
1. **Update from RBI** (recommended) — downloads the official PDFs in `regulatory_kb/sources.yaml`: the consolidated
   NBFC and bank Directions plus each Amendment Direction. Unchanged files are skipped; changed files become a new
   dated version and the changed paragraphs are logged.
2. **Check RBI for new notices** — reads RBI's official RSS feeds (notifications, press releases), shortlists
   capital-adequacy items and indexes the one you choose (it follows the notice page to the official PDF).
3. **Offline** — upload a PDF, drop it in `regulatory_kb/library/`, or add any RBI URL as a source.

**Which rules apply to a run: the reporting date decides.** A 31-Mar-2026 run uses only text in force on
31-Mar-2026. Later rules are kept, shown as "newer — not applied", and apply automatically to runs with a later
reporting date. Dates are read from the text: *"applicable from <date>"* (e.g. the 1-Jan-2026 amendment applies
from 1-Apr-2026), *"with immediate effect"*, *"Updated as on"*, and amendments referenced inside consolidated text
(RBI updates consolidated PDFs in place, so today's copy is dated by the latest amendment it contains).

**Safeguards:** drafts are stored but never used; scanned PDFs and JavaScript-only pages are detected and explained;
downloads retry with back-off and honour `HTTPS_PROXY` and a corporate CA bundle (`CAPITAL_AGENT_CA_BUNDLE`); an SME
can correct any detected date (logged). When RBI changes a paragraph an approved rule cites, the rule is flagged
for re-approval (`EXC-RBI-<rule>` if the change is in force for the run, `EXC-RBI-FUTURE` if later). If no full RBI
text is in force on the reporting date, `EXC-RBI-COVERAGE` says so.

Command line: `python -m capital_agent.rag_store refresh` (can be scheduled with Windows Task Scheduler).

## v1.1 — every page is a Command-Centre page
Tier 1, Tier 2, RWA, Derivatives, Sensitivity, Rules in force, Agent reasoning, Validation, Audit trail, Exception
queue and RBI library all use the same component: drill-down panels that open **over** the page (nothing
shrinks), sortable/searchable/filterable tables, instant scenario toggles, day/night theme, and page search that
hands questions to the agent. The sidebar slides over the dashboard instead of narrowing it.

## v1.2 — Basel III, fetching explained, flaws fixed

**Basel III lens** (`capital_agent/basel3.py`, page *Basel III lens*): CET1 / AT1 / Tier 2 stack, ratios against the
BCBS floor, RBI minimum (CET1 5.5%, Tier 1 7%, total 9%) and RBI with buffers (CCB 2.5%, CCyB 0-2.5%, D-SIB
0.20-0.80%); leverage ratio (Tier 1 / exposure; 3.5%, or 4% for D-SIBs); the CCB distribution-restriction band;
live dials for D-SIB, CCyB and an illustrative market/operational-risk add-on. Binding for banks; a benchmark lens
for NBFCs, whose compliance verdict comes from the NBFC Directions.

**How fetching works.** "Update from RBI" and "Check RBI for new notices" make ordinary HTTPS GET requests to RBI's
public website - the same request a browser makes when you open the PDF. No API key or login is involved (the API key
discussed earlier was only ever for an AI model, which this offline build does not use). Nothing about the client is
sent; requests run only when someone clicks the button (or a scheduled `python -m capital_agent.rag_store refresh`).
Downloads are limited to `https://*.rbi.org.in` (override: `CAPITAL_AGENT_ALLOWED_DOMAINS`) and 60 MB.

**Flaws fixed in v1.2:** non-RBI URLs refused; size cap; re-published PDFs with identical text no longer create
versions; early-adoption wording flagged; near-miss notices kept as "Possible"; feeds-stale warning (RSS keeps only
recent items); RBI "Previous Versions" importer for exact historical text; sidebar override removed (Streamlit's
own collapse button is back).

## v1.3 — desktop layout, whole-app night mode, power features
- **Full desktop width** (no 1,380 px cap) and a compact density by default: the Command Centre is ~15% shorter.
- **Night mode for the whole app**: the dashboard's day/night switch now also darkens Streamlit's sidebar, background
  and controls, and every page opens in the chosen theme.
- **Tabs no longer leave blank space**: a fixed-height panel with internal scrolling.
- **Command palette** (Ctrl/⌘+K): jump to any page, toggle theme or density, or ask the agent.
- **Expand any card** (⤢) into a large panel over the page; **icons on every card**; **mini-charts** in KPI tiles.
- **Shortcuts**: `?` help · `T` theme · `D` density · `/` search · `Esc` close.

## v1.4 — management review changes
- **Calculation (step by step)** page and **Calculation ledger CSV** (`capital_agent/ledger.py`): every step from source
  cell to CRAR with input, treatment, formula, result, running total, rule and RBI paragraph. The ledger re-derives
  every total itself and checks it against the engine (Tier 1, Tier 2, RWA, derivatives RWA, total RWA, CRAR, Tier 1
  ratio); the CSV opens in Excel (UTF-8 with BOM) and its columns re-add to the reported figures.
- **RBI nomenclature**: the official RBI title, RBI reference (e.g. RBI/DOR/2025-26/345), circular number and date are
  read from each downloaded document and shown in the **RBI register** ("What's in the system"), with status:
  Current / Superseded / Draft - never applied / Curated summary - not an RBI document. `sources.yaml` now uses RBI's
  official titles; an SME can correct a name or reference (logged).
- **Management memo** (`capital_agent/memo.py`): one-page printable summary with figures, compliance, Basel III lens,
  open judgement calls, RBI texts applied and newer texts not applied (by official name and reference), controls and
  a sign-off block. Download from the Calculation page or the sidebar; open it and Print → Save as PDF.
- **Run history**: each re-run this session with its CRAR change (e.g. after SME decisions).
