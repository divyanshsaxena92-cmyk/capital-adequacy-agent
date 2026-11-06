"""Make hand-built HTML survive Streamlit's st.html sanitiser (DOMPurify).

Two DOMPurify behaviours silently strip styling:
1. A <style> block at the very start of the HTML is parsed into <head> and discarded.
2. A <style> block whose text contains "<" (e.g. @property syntax '<integer>') is removed as unsafe.
So: merge every <style> into one block, escape "<" inside the CSS as \\3C (CSS reads it back as "<"),
and place the block inside a wrapping <div>.
"""
import re


def prepare(html: str) -> str:
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I))
    body = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    css = css.replace("<", "\\3C ")      # only "<" trips the sanitiser; ">" is a CSS child combinator
    return f'<div class="gt-html"><style>{css}</style>{body}</div>'
