"""Minimal stand-in for the streamlit module so app.py and every tab can be executed headless in CI.

It records calls, returns sensible widget defaults, and sanity-checks data passed to tables/charts.
Not a replacement for running `streamlit run app.py` - a smoke test that every code path executes.
"""
import types

import pandas as pd

CALLS = []
BUTTONS = {}        # key/label -> value to return
FILE = {"upload": None}
CHAT = {"q": None}  # value st.chat_input returns
PAGES = []          # titles of pages registered with st.navigation


class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v


class _Rerun(BaseException):   # like Streamlit's ScriptControlException: not caught by `except Exception`
    pass


class Elem:
    """Anything that can be a container (sidebar, column, tab, expander)."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    # --- output
    def _rec(self, name, *a, **k):
        CALLS.append((name, a, k))

    def markdown(self, *a, **k): self._rec("markdown", *a, **k)
    def caption(self, *a, **k): self._rec("caption", *a, **k)
    def subheader(self, *a, **k): self._rec("subheader", *a, **k)
    def code(self, *a, **k): self._rec("code", *a, **k)
    def divider(self, *a, **k): self._rec("divider")
    def info(self, *a, **k): self._rec("info", *a)
    def success(self, *a, **k): self._rec("success", *a)
    def warning(self, *a, **k): self._rec("warning", *a)
    def error(self, *a, **k): self._rec("error", *a)
    def toast(self, *a, **k): self._rec("toast", *a)
    def progress(self, v, text=None):
        assert 0 <= v <= 1
        self._rec("progress", v)
        return Elem()

    def empty(self): return Elem()
    def text(self, *a, **k): self._rec("text", *a)
    def write(self, *a, **k): self._rec("write", *a)
    def date_input(self, label, value=None, key=None, **k): return value
    def number_input(self, label, min_value=None, value=0, key=None, **k): return value

    def metric(self, label, value, delta=None, **k):
        assert isinstance(value, (str, int, float)), (label, value)
        self._rec("metric", label, value, delta)

    def dataframe(self, df, **k):
        assert isinstance(df, pd.DataFrame)
        cfg = k.get("column_config") or {}
        for col in cfg:
            assert col in df.columns, f"column_config refers to missing column {col!r}; have {list(df.columns)}"
        self._rec("dataframe", df.shape)

    def data_editor(self, df, **k):
        for col in (k.get("column_config") or {}):
            assert col in df.columns, col
        for col in k.get("disabled", []):
            assert col in df.columns, col
        self._rec("data_editor", df.shape)
        return df

    def bar_chart(self, df, **k):
        assert isinstance(df, pd.DataFrame) and len(df.columns)
        for c in df.columns:
            assert pd.api.types.is_numeric_dtype(df[c]), f"non-numeric chart column {c}"
        self._rec("bar_chart", df.shape)

    def download_button(self, label, data, **k):
        assert isinstance(data, (bytes, str)) and len(data) > 0, label
        self._rec("download_button", label, len(data))

    # --- containers
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [Elem() for _ in range(n)]

    def tabs(self, names):
        self._rec("tabs", names)
        return [Elem() for _ in names]

    def expander(self, *a, **k): return Elem()
    def spinner(self, *a, **k): return Elem()

    # --- widgets
    def button(self, label, key=None, on_click=None, **k):
        self._rec("button", label)
        v = BUTTONS.get(key or label, False)
        if v and on_click:
            on_click()
        return v
    def container(self, *a, **k): return Elem()
    def chat_message(self, role, **k): self._rec("chat_message", role); return Elem()
    def chat_input(self, *a, **k): return CHAT["q"]
    def altair_chart(self, chart, **k): self._rec("altair_chart")
    def html(self, body, **k):
        assert isinstance(body, str) and body
        self._rec("html", body)
    def page_link(self, page, label=None, icon=None, **k):
        assert hasattr(page, "fn"), "page_link needs an st.Page"
        self._rec("page_link", label)
    def toggle(self, label, value=False, key=None, **k): return BUTTONS.get(key, value)
    def file_uploader(self, label, key=None, **k):
        self._rec("file_uploader", label)
        return FILE["upload"] if key is None else None
    def radio(self, label, options, **k): return options[0]
    def text_input(self, label, value="", key=None, **k):     # like Streamlit: typed value lives in session_state[key]
        return module.session_state.get(key, value) if key else value
    def slider(self, label, min_value=None, max_value=None, value=None, step=None, **k): return value

    def selectbox(self, label, options, format_func=None, **k):
        options = list(options)
        if format_func:
            for o in options:
                assert isinstance(format_func(o), str)
        return options[0] if options else None

    def multiselect(self, label, options, default=None, **k): return list(default or [])


_root = Elem()
module = types.ModuleType("streamlit")
for _name in dir(Elem):
    if not _name.startswith("__"):
        setattr(module, _name, getattr(_root, _name))
module.sidebar = Elem()


class _Page:
    def __init__(self, fn, title=None, icon=None, url_path=None, default=False):
        self.fn, self.title, self.icon, self.url_path = fn, title, icon, url_path


class _Nav:
    def __init__(self, pages):
        self.pages = pages

    def run(self):            # the stub renders EVERY page so tests cover them all
        for sec, items in self.pages.items():
            for p in items:
                CALLS.append(("page", (sec, p.title), {}))
                p.fn()


def _navigation(pages, **k):
    PAGES.clear()
    PAGES.extend(p.title for items in pages.values() for p in items)
    paths = [p.url_path for items in pages.values() for p in items]
    assert len(paths) == len(set(paths)), "duplicate url_path"
    return _Nav(pages)


module.Page = _Page
COMPONENT = {"return": None, "key": "cc"}   # like Streamlit: a component instance only returns its own value


def _switch_page(page):
    CALLS.append(("switch_page", (getattr(page, "title", page),), {}))
    raise _Rerun()


module.switch_page = _switch_page
_components = types.ModuleType("streamlit.components")
_v1 = types.ModuleType("streamlit.components.v1")


def _declare_component(name, path=None, url=None):
    import os as _os
    assert path and _os.path.exists(_os.path.join(path, "index.html")), "component needs index.html"

    def _call(**kw):
        CALLS.append(("component", (name,), kw))
        return COMPONENT["return"] if kw.get("key") == COMPONENT["key"] else None
    return _call


_v1.declare_component = _declare_component
_v1.html = lambda *a, **k: None
_components.v1 = _v1
module.components = _components
module.navigation = _navigation
module.session_state = _SessionState()
module.set_page_config = lambda **k: None
module.rerun = lambda: (_ for _ in ()).throw(_Rerun())
module.Rerun = _Rerun
Rerun = _Rerun
cc = types.SimpleNamespace()
for _n in ("NumberColumn", "ProgressColumn", "LinkColumn", "SelectboxColumn", "TextColumn", "CheckboxColumn"):
    setattr(cc, _n, lambda *a, **k: {"a": a, "k": k})
module.column_config = cc
