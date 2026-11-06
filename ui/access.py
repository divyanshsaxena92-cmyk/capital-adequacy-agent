"""Viewer mode for hosted deployments: everyone can explore; only an admin can change data.

Turn on with  CAPITAL_AGENT_MODE=viewer  (environment) or  mode = "viewer"  in Streamlit secrets.
Admin password:  CAPITAL_AGENT_ADMIN_PASSWORD  or  admin_password  in secrets - never in the code or the repository.
Viewer mode blocks: client-workbook upload, RBI downloads / uploads / corrections, large-data import and deletion.
Code and repository content (e.g. RBI PDFs in regulatory_kb/library/) change only through GitHub.
"""
import hmac
import os


def _secret(st, key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:                       # no secrets file locally
        return default


def mode(st) -> str:
    return str(os.environ.get("CAPITAL_AGENT_MODE") or _secret(st, "mode", "full")).lower()


def is_admin(st) -> bool:
    return mode(st) != "viewer" or bool(st.session_state.get("is_admin"))


def admin_panel(st):
    if mode(st) != "viewer":
        return
    ss = st.session_state
    with st.sidebar.expander("Admin ✓" if ss.get("is_admin") else "Admin sign-in"):
        if ss.get("is_admin"):
            st.caption("You can upload workbooks and change the RBI knowledge base.")
            if st.button("Sign out", key="adm-out"):
                ss.is_admin = False
                st.rerun()
            return
        st.caption("View-only for visitors. Admins can upload and update.")
        pw = st.text_input("Admin password", type="password", key="adm-pw")
        if st.button("Sign in", key="adm-in"):
            expected = os.environ.get("CAPITAL_AGENT_ADMIN_PASSWORD") or str(_secret(st, "admin_password", ""))
            if expected and hmac.compare_digest(str(pw or ""), expected):
                ss.is_admin = True
                st.rerun()
            else:
                st.error("Incorrect password.")


def read_only_note(st, theme, what: str):
    theme.note(st, f"<b>View-only.</b> {what} is limited to admins on this hosted copy. Sign in under <b>Admin</b> in the sidebar.")
