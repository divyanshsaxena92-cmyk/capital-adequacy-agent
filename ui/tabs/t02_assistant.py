"""Ask the Agent - offline Q&A over this run and the RBI knowledge base. No LLM: every answer is computed
from the engine or quoted from RBI text, with paragraph references."""
from capital_agent.assistant import Assistant
from ui import theme


def _sources(st, srcs):
    if not srcs:
        return
    with st.expander(f"Sources ({len(srcs)})"):
        for s in srcs:
            head = f"**para {s['para']}**" + (f" · {s['title'][:80]}" if s.get("title") else "")
            st.markdown(head)
            if s.get("snippet"):
                st.caption(s["snippet"] + ("…" if len(s["snippet"]) >= 240 else ""))
            if s.get("url", "").startswith("http"):
                st.markdown(f"[Open RBI source]({s['url']})")


def render(ctx):
    st = ctx.st
    ss = st.session_state
    ss.setdefault("chat", [])
    bot = Assistant(ctx.run, ctx.extra["rag"])
    theme.note(st, "Answers come from this run's results and from RBI text in the knowledge base. "
                   "Nothing is generated and nothing leaves this machine — every figure is computed by the "
                   "engine and every regulatory answer is quoted with its paragraph number.")

    pending = None
    if not ss.chat:
        theme.section(st, "Try asking")
        sugg = Assistant.SUGGESTED if ctx.run is not None else \
            ["How is Tier 2 capped?", "What risk weight applies to gold loans?", "How are deferred tax assets treated?"]
        cols = st.columns(3, gap="small")
        for i, q in enumerate(sugg):
            if cols[i % 3].button(q, key=f"sugg-{i}", width="stretch"):
                pending = q

    for msg in ss.chat:
        with st.chat_message(msg["role"], avatar=":material/person:" if msg["role"] == "user" else ":material/menu_book:"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _sources(st, msg.get("sources"))

    q = st.chat_input("Ask about this run or the RBI rules — e.g. “what if loans are at 100%?”") or pending
    if q:
        ans = bot.ask(q)
        ss.chat.append({"role": "user", "content": q})
        ss.chat.append({"role": "assistant", "content": ans.text, "sources": ans.sources,
                        "followups": ans.followups})
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(q)
        with st.chat_message("assistant", avatar=":material/menu_book:"):
            st.markdown(ans.text)
            _sources(st, ans.sources)
    if ss.chat:
        last = ss.chat[-1]
        fu = [f for f in last.get("followups", []) if f]
        if fu:
            cols = st.columns(len(fu[:3]), gap="small")
            for i, f in enumerate(fu[:3]):
                if cols[i].button(f, key=f"fu-{len(ss.chat)}-{i}", width="stretch"):
                    a = bot.ask(f)
                    ss.chat += [{"role": "user", "content": f},
                                {"role": "assistant", "content": a.text, "sources": a.sources,
                                 "followups": a.followups}]
                    st.rerun()
        if st.button("Clear conversation", key="chat-clear"):
            ss.chat = []
            st.rerun()


TAB = {"title": "Ask the Agent", "section": "Dashboard", "icon": ":material/forum:", "order": 20,
       "subtitle": "Plain-English answers about this run and RBI's rules — offline, with citations",
       "render": render, "needs_run": False}
