"""Registers the Command-Centre component (served from ui/dashboard_component) and handles its events."""
import os

import streamlit.components.v1 as components

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_component")
_component = components.declare_component("gt_command_centre", path=_DIR)


def command_centre(html: str, data: dict, key: str = "cc"):
    """Render; returns the last user action ({type: 'ask'|'nav', ...}) or None."""
    return _component(html=html, data=data, key=key, default=None)


def show(ctx, html: str, data: dict, key: str):
    """Render a component page and act on its events: search -> Ask the Agent, clicks -> other pages."""
    st = ctx.st
    ss = st.session_state
    data = dict(data or {})
    data["theme"] = ss.get("theme", "light")                       # one theme for the whole app
    data["commands"] = ctx.extra.get("commands", [])               # command palette: every page
    ev = command_centre(html, data, key=key)
    if not ev or ev.get("nonce") == ss.get(f"{key}_nonce"):
        return
    ss[f"{key}_nonce"] = ev.get("nonce")
    pages = ctx.extra.get("pages", {})
    if ev.get("type") == "ask" and ev.get("q"):
        from capital_agent.assistant import Assistant
        a = Assistant(ctx.run, ctx.extra["rag"]).ask(ev["q"])
        ss.setdefault("chat", [])
        ss.chat += [{"role": "user", "content": ev["q"]},
                    {"role": "assistant", "content": a.text, "sources": a.sources, "followups": a.followups}]
        if "t02_assistant" in pages:
            st.switch_page(pages["t02_assistant"])
    elif ev.get("type") == "nav" and ev.get("page") in pages:
        st.switch_page(pages[ev["page"]])
    elif ev.get("type") == "theme" and ev.get("value") in ("light", "dark"):
        if ss.get("theme", "light") != ev["value"]:
            ss.theme = ev["value"]
            st.rerun()
