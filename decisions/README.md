# SME decisions

After a draft run, `decisions_template.csv` lists every open exception. The regulatory SME fills in:

| column | values |
|---|---|
| decision | `ACCEPT_ALTERNATIVE` (apply the alternative treatment quantified in the queue), `RETAIN_BASELINE`, `NOTED` (information items) |
| reviewer | name / ID - **required**; unsigned decisions are ignored |
| comment | basis for the decision (firm methodology, evidence seen) |

Then re-run: `python run_agent.py --input <file> --decisions decisions/decisions.csv`.
Every decision is written to the audit trail with the reviewer's name. The agent never fills this file itself.
