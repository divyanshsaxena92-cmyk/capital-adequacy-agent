"""What-if simulator: switch judgement calls on/off and move risk weights; the engine recomputes instantly."""
import pandas as pd

from ui import charts, theme
from ui.theme import lakhs


def render(ctx):
    st, run = ctx.st, ctx.run
    base, m = run.final, run.minimums
    theme.note(st, "A sandbox for the reviewer. Nothing here changes the reported figures — to adopt a change, "
                   "record the decision in the <b>Exception queue</b>.")
    scen = [e for e in run.exceptions if e.status == "OPEN" and e.scenario_overrides
            and ("capital" in e.scenario_overrides or "ccr_rw" in e.scenario_overrides)]
    loans = next(a for a in run.rwa_applied if a.cls.label == "Loans")

    left, right = st.columns([2, 3], gap="large")
    ov = {"capital": {}, "rwa": {}}
    applied = []
    with left:
        theme.section(st, "Judgement calls")
        for e in scen:
            label = e.title.split(":")[0][:48]
            on = st.toggle(f"{label}  ({e.impact_crar_bps:+.0f} bps)", key=f"wi-{e.exc_id}",
                           help=e.scenario_desc.split(" =>")[0])
            if on:
                for k, v in e.scenario_overrides.items():
                    if isinstance(v, dict):
                        ov[k].update(v)
                    else:
                        ov[k] = v
                applied.append(label)
        theme.section(st, "Loan book risk weight")
        rw = st.slider("Risk weight on loans (%)", min_value=0, max_value=150, value=int(round(loans.applied * 100)),
                       step=5, key="wi-loans",
                       help="125% = unsecured retail / credit card; 100% = secured carve-outs (para 18(1))")
        if rw / 100 != loans.applied:
            ov["rwa"][loans.cls.item_id] = rw / 100
            applied.append(f"Loans at {rw}%")
        def _reset():
            for e in scen:
                st.session_state[f"wi-{e.exc_id}"] = False
            st.session_state["wi-loans"] = int(round(loans.applied * 100))
        st.button("Reset to reported position", key="wi-reset", on_click=_reset)

    new = run._compute(ov)
    with right:
        theme.section(st, "Result")
        d = (new.crar - base.crar) * 1e4
        theme.kpis(st, [
            {"label": "CRAR", "value": f"{new.crar:.2%}", "tone": "bad" if new.crar < m["crar"] else "ok",
             "delta": f"{d:+.0f} bps vs reported", "delta_tone": "ok" if d >= 0 else "bad"},
            {"label": "Tier 1 ratio", "value": f"{new.tier1_ratio:.2%}",
             "tone": "bad" if new.tier1_ratio < m["tier1"] else "ok",
             "delta": f"{(new.tier1_ratio - base.tier1_ratio) * 1e4:+.0f} bps vs reported",
             "delta_tone": "ok" if new.tier1_ratio >= base.tier1_ratio else "bad"},
            {"label": "Tier 1 capital", "value": lakhs(new.tier1), "delta": f"{new.tier1 - base.tier1:+,.0f} L"},
            {"label": "Total RWA", "value": lakhs(new.total_rwa), "delta": f"{new.total_rwa - base.total_rwa:+,.0f} L"},
        ])
        charts.ratio_bullet(st, pd.DataFrame({"label": ["CRAR", "Tier 1 ratio"],
                                              "actual": [new.crar * 100, new.tier1_ratio * 100],
                                              "minimum": [m["crar"] * 100, m["tier1"] * 100]}), height=160)
        if new.breaches:
            st.error("Breach: " + "; ".join(new.breaches))
        theme.kv(st, [("Changes applied", ", ".join(applied) if applied else "none — this is the reported position"),
                      ("Capital above CRAR minimum", lakhs(new.tier1 + new.tier2 - m["crar"] * new.total_rwa))])


TAB = {"title": "What-if simulator", "section": "Review", "icon": ":material/tune:", "order": 65,
       "subtitle": "Flip any judgement call or change the loan risk weight and watch the ratios move", "render": render}
