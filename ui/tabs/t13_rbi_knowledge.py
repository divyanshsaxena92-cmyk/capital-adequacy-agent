"""RBI library - the brain. Visual health/timeline/drift/changes (component) + the actions that keep it current."""
import datetime as dt
import re

import pandas as pd

from capital_agent import rbi_brain
from capital_agent.rag_store import load_sources, save_sources
from ui import pages_rbi, theme
from ui.component import show
from ui.widgets import table


def render(ctx):
    st, rag = ctx.st, ctx.extra["rag"]
    src_path = ctx.extra["sources_path"]
    if ctx.run is not None:
        html, data = pages_rbi.build(ctx.run, rag)
        show(ctx, html, data, "t13_rbi")

    from ui import access
    if not access.is_admin(st):
        access.read_only_note(st, theme, "Updating the RBI knowledge base")
        with st.expander("Test the brain: search RBI text as of a date"):
            q = st.text_input("Question or keywords", value="statutory reserve tier 1 capital", key="rbi-q-ro")
            asof = st.date_input("As of", value=ctx.run.ds.reporting_date if ctx.run else dt.date.today(), key="rbi-asof-ro")
            if q:
                for h in rag.search(q, k=6, as_of=asof):
                    st.markdown(f"**para {h.para}** · {h.title[:70]} · v{h.version} · in force from {h.effective_from}")
                    st.caption(h.text[:400])
        return
    theme.section(st, "Keep the brain current")
    a, b, c = st.columns(3, gap="medium")
    with a:
        st.markdown("**1 · Update from RBI**  \nDownloads the official PDFs in `sources.yaml`; changed files become new dated versions.")
        if st.button("Update from RBI", type="primary", key="rbi-update", width="stretch"):
            bar = st.progress(0.0, text="Starting")
            res = rbi_brain.update_from_rbi(rag, load_sources(src_path), lambda p, m: bar.progress(min(p, 1.0), text=m))
            table(st, pd.DataFrame([{"Official RBI name": r.get("official_title") or "", "RBI reference": r.get("ref_no") or "",
                                     "Result": r.get("action"), "Version": r.get("version"), "Type": r.get("kind"),
                                     "In force from": r.get("effective_from"), "Paragraphs changed": r.get("paragraphs_changed"),
                                     "Detail": r.get("detail") or r.get("basis") or "", "Internal ID": r.get("source")} for r in res]))
            if any(r.get("action") in ("error", "rejected") for r in res):
                st.warning("Some downloads failed - see the reason in the table. On a corporate network set HTTPS_PROXY or "
                           "CAPITAL_AGENT_CA_BUNDLE, or save the PDF in a browser and use route 3.")
    with b:
        st.markdown("**2 · Check RBI for new notices**  \nReads RBI's official notification and press-release feeds.")
        if st.button("Check RBI for new notices", key="rbi-feeds", width="stretch"):
            s = rbi_brain.check_feeds(rag)
            (st.success if not s["errors"] else st.warning)(
                f"{len(s['new'])} new capital-adequacy notice(s). " + ("; ".join(s["errors"]) if s["errors"] else ""))
        new = rbi_brain.watch_items(rag, "NEW")
        if new:
            pick = st.selectbox("New notices", [w["guid"] for w in new], key="rbi-pick",
                                format_func=lambda g: next(f"[{w['kind']}] {w['title'][:90]}" for w in new if w["guid"] == g))
            x, y = st.columns(2)
            if x.button("Index this notice", key="rbi-index", width="stretch"):
                r = rbi_brain.index_watch_item(rag, pick)
                (st.success if r.get("action") in ("indexed", "new version", "unchanged") else st.error)(
                    f"{r.get('action')}: kind {r.get('kind', '-')}, effective {r.get('effective_from', '-')} {r.get('detail', '')}")
            if y.button("Dismiss", key="rbi-dismiss", width="stretch"):
                rbi_brain.dismiss_watch_item(rag, pick)
                st.rerun()
    with c:
        st.markdown(f"**3 · Library folder (offline)**  \nPDFs placed here are indexed:")
        st.code(ctx.extra.get("library", ""), language=None)
        if st.button("Index library folder", key="rbi-lib", width="stretch"):
            res = rag.ingest_folder(ctx.extra.get("library", ""))
            st.info(f"{len(res)} file(s): " + ", ".join(f"{r.get('file')}: {r.get('action')}" for r in res) if res else
                    "No PDF files in the folder yet.")

    with st.expander("Upload an RBI PDF or saved page"):
        up = st.file_uploader("RBI document", type=["pdf", "html", "htm"], key="rbi-up")
        u1, u2, u3 = st.columns(3)
        title = u1.text_input("Title", key="rbi-up-title")
        fw = u2.selectbox("Framework", ["NBFC", "BANK"], key="rbi-up-fw")
        mode = u3.selectbox("Effective date", ["Read from the document", "Set manually"], key="rbi-up-mode")
        eff = st.date_input("Effective from", value=dt.date.today(), key="rbi-up-eff") if mode == "Set manually" else None
        if st.button("Index document", key="rbi-up-go") and up is not None:
            sid = re.sub(r"[^A-Za-z0-9]+", "-", title or up.name).strip("-")[:48].upper()
            srcd = {"id": sid, "title": title or up.name, "type": "pdf" if up.name.lower().endswith(".pdf") else "html",
                    "framework": fw, "url": f"upload:{up.name}"}
            if eff:
                srcd["effective_override"] = eff.isoformat()
            r = rag.ingest(srcd, up.getvalue(), origin="upload")
            (st.success if r["action"] in ("indexed", "new version", "unchanged") else st.error)(
                f"{r['action']}: kind {r.get('kind', '-')}, in force from {r.get('effective_from', '-')} "
                f"({r.get('basis', '')}) {r.get('detail', '')}")

    with st.expander("Add an RBI source URL"):
        s1, s2 = st.columns(2)
        url = s1.text_input("RBI PDF or notification URL", key="rbi-url")
        ttl = s2.text_input("Title", key="rbi-url-title")
        fw2 = st.selectbox("Framework", ["NBFC", "BANK"], key="rbi-url-fw")
        if st.button("Add to sources", key="rbi-url-add"):
            if not url.startswith("http") or not ttl:
                st.error("Enter a full https:// URL and a title.")
            elif not rbi_brain.domain_allowed(url):
                st.error("Only RBI addresses (https://*.rbi.org.in) are downloaded. For any other source, download the PDF "
                         "yourself and use 'Upload an RBI PDF'.")
            else:
                srcs = load_sources(src_path)
                sid = re.sub(r"[^A-Za-z0-9]+", "-", ttl).strip("-")[:40].upper()
                srcs.append({"id": sid, "title": ttl, "url": url, "type": "pdf" if url.lower().endswith(".pdf") else "html",
                             "framework": fw2, "enabled": True})
                save_sources(src_path, srcs)
                st.success(f"Added {sid}. Dates are read from the document when you press Update from RBI.")

    with st.expander("Import exact historical versions (RBI 'Previous Versions' page)"):
        st.caption("Each RBI Master Direction has a 'Previous Versions' page listing 'Updated as on <date>' copies. Importing it "
                   "gives every version its exact in-force window, so a run for any past date uses the text in force then.")
        pv_url = st.text_input("Previous-versions page URL (https://www.rbi.org.in/Scripts/NotificationPreVersion.aspx?id=...)", key="rbi-pv-url")
        p1, p2, p3 = st.columns(3)
        pv_id = p1.text_input("Document ID", value="NBFC-CA-2025", key="rbi-pv-id")
        pv_title = p2.text_input("Title", value="RBI NBFC Capital Adequacy Directions, 2025", key="rbi-pv-title")
        pv_fw = p3.selectbox("Framework", ["NBFC", "BANK"], key="rbi-pv-fw")
        if st.button("Import previous versions", key="rbi-pv-go"):
            if not rbi_brain.domain_allowed(pv_url):
                st.error("Enter an https://www.rbi.org.in previous-versions page URL.")
            else:
                try:
                    res = rbi_brain.import_previous_versions(rag, pv_url, pv_id, pv_title, pv_fw)
                    st.success(f"{len(res)} dated version(s) processed.") if res else st.warning("No 'Updated as on' links found on that page.")
                    if res:
                        table(st, pd.DataFrame([{k: r.get(k) for k in ("as_on", "in_force_to", "action", "detail")} for r in res]))
                except Exception as e:
                    st.error(str(e))

    possible = rbi_brain.watch_items(rag, "POSSIBLE")
    if possible:
        with st.expander(f"Possibly relevant RBI notices ({len(possible)}) - below the relevance cut-off"):
            st.caption("Kept so nothing is silently missed. Index one if it affects capital adequacy.")
            pk = st.selectbox("Notice", [w["guid"] for w in possible], key="rbi-pos-pick",
                              format_func=lambda g: next(w["title"][:100] for w in possible if w["guid"] == g))
            if st.button("Index this notice", key="rbi-pos-index"):
                r = rbi_brain.index_watch_item(rag, pk)
                st.info(f"{r.get('action')}: {r.get('detail', '')}")

    with st.expander("Correct the RBI name / reference (SME, logged)"):
        rows = [c for c in rbi_brain.catalogue(rag) if c["kind"] != "curated"]
        if not rows:
            st.caption("No RBI documents loaded yet.")
        else:
            k = st.selectbox("Document", [f"{c['doc_id']}|{c['version']}" for c in rows], key="rbi-nm-doc",
                             format_func=lambda x: next(f"{(c['official_title'] or c['our_label'])[:90]} - {c['ref_no'] or 'no ref'} (v{c['version']})"
                                                        for c in rows if f"{c['doc_id']}|{c['version']}" == x))
            cur = next(c for c in rows if f"{c['doc_id']}|{c['version']}" == k)
            t_ = st.text_input("Official RBI title", value=cur["official_title"], key=f"rbi-nm-t-{k}")
            n1, n2, n3 = st.columns(3)
            r_ = n1.text_input("RBI reference (e.g. RBI/DOR/2025-26/345)", value=cur["ref_no"], key=f"rbi-nm-r-{k}")
            c_ = n2.text_input("Circular number (DOR....)", value=cur["circular_no"], key=f"rbi-nm-c-{k}")
            w_ = n3.text_input("Reviewer (required)", key="rbi-nm-who")
            if st.button("Save name / reference", key="rbi-nm-go"):
                if not w_.strip():
                    st.error("Reviewer name is required.")
                else:
                    d_id, ver = k.split("|")
                    rbi_brain.set_nomenclature(rag, d_id, int(ver), t_, r_, c_, w_.strip())
                    st.success("Saved and logged.")

    with st.expander("Correct a detected effective date (SME, logged)"):
        docs = [d for d in rag.documents() if not d["origin"].startswith("curated")]
        if not docs:
            st.caption("No RBI documents loaded yet.")
        else:
            key = st.selectbox("Document version", [f"{d['doc_id']}|{d['version']}" for d in docs], key="rbi-ov-doc",
                               format_func=lambda k: next(f"{d['doc_id']} v{d['version']} - in force from {d['effective_from']}"
                                                          for d in docs if f"{d['doc_id']}|{d['version']}" == k))
            o1, o2 = st.columns(2)
            nd = o1.date_input("Correct effective date", key="rbi-ov-date")
            who = o2.text_input("Reviewer (required)", key="rbi-ov-who")
            if st.button("Apply correction", key="rbi-ov-go"):
                if not who.strip():
                    st.error("Reviewer name is required.")
                else:
                    d_id, ver = key.split("|")
                    rbi_brain.set_effective_override(rag, d_id, int(ver), nd.isoformat(), who.strip())
                    st.success("Date corrected and logged. Re-run the agent to apply it.")

    with st.expander("Test the brain: search RBI text as of a date"):
        q = st.text_input("Question or keywords", value="statutory reserve tier 1 capital", key="rbi-q")
        asof = st.date_input("As of", value=ctx.run.ds.reporting_date if ctx.run else dt.date.today(), key="rbi-asof")
        if q:
            for h in rag.search(q, k=6, as_of=asof):
                st.markdown(f"**para {h.para}** · {h.title[:70]} · v{h.version} · in force from {h.effective_from}")
                st.caption(h.text[:400])

    if ctx.run is not None and st.button("Re-run the agent with the updated knowledge base", key="rbi-rerun"):
        ctx.rerun([])


TAB = {"title": "RBI library", "section": "Regulation", "icon": ":material/menu_book:", "order": 10,
       "subtitle": "The brain: RBI text, versions, changes and new notices", "render": render, "needs_run": False, "bare": True}
