"""ansi.py — ANSI SGR escape sequences → inline-styled HTML."""
import html
import re

_ANSI_C16 = [
    "#3b4048", "#e06c75", "#98c379", "#e5c07b",
    "#61afef", "#c678dd", "#56b6c2", "#d8dee4",
    "#5c6370", "#ff6b6b", "#a8e05f", "#ffd866",
    "#82aaff", "#c792ea", "#73d0ff", "#ffffff",
]


def _xterm_rgb(n: int) -> str:
    if n < 16:
        return _ANSI_C16[n]
    if n < 232:
        n -= 16
        c = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (c[n // 36], c[(n // 6) % 6], c[n % 6])
    v = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (v, v, v)


def ansi_to_html(s: str) -> str:
    """Convert ANSI SGR sequences to inline-styled HTML spans."""
    if not s:
        return ""
    fg = bg = None
    bold = italic = underline = False
    out: list[str] = []
    pending = ""
    ptr = 0

    def style_str() -> str:
        st = []
        if bold:
            st.append("font-weight:700")
        if italic:
            st.append("font-style:italic")
        if underline:
            st.append("text-decoration:underline")
        if fg:
            st.append("color:" + fg)
        if bg:
            st.append("background:" + bg)
        return ";".join(st)

    def emit_text(text: str) -> None:
        nonlocal pending
        if not text:
            return
        if pending:
            out.append('<span style="%s">' % pending)
            out.append(html.escape(text))
            out.append("</span>")
            pending = ""
        else:
            out.append(html.escape(text))

    def apply(params: list[int]) -> None:
        nonlocal fg, bg, bold, italic, underline
        if not params:
            params = [0]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                fg = bg = None
                bold = italic = underline = False
            elif p == 1:
                bold = True
            elif p == 3:
                italic = True
            elif p == 4:
                underline = True
            elif p == 22:
                bold = False
            elif p == 23:
                italic = False
            elif p == 24:
                underline = False
            elif 30 <= p <= 37:
                fg = _ANSI_C16[p - 30]
            elif 90 <= p <= 97:
                fg = _ANSI_C16[p - 90 + 8]
            elif p == 39:
                fg = None
            elif 40 <= p <= 47:
                bg = _ANSI_C16[p - 40]
            elif 100 <= p <= 107:
                bg = _ANSI_C16[p - 100 + 8]
            elif p == 49:
                bg = None
            elif p in (38, 48) and i + 2 < len(params) and params[i + 1] == 5:
                col = _xterm_rgb(params[i + 2])
                i += 2
                if p == 38:
                    fg = col
                else:
                    bg = col
            elif p in (38, 48) and i + 4 < len(params) and params[i + 1] == 2:
                col = "#%02x%02x%02x" % (params[i + 2], params[i + 3], params[i + 4])
                i += 4
                if p == 38:
                    fg = col
                else:
                    bg = col
            i += 1

    for m in re.finditer(
        r"\x1b\[([0-9;]*)m"
        r"|\x1b\[[0-9;?]*[A-Za-z]"
        r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
        r"|\x1b[()][A-Za-z0-9]"
        r"|\x1b.",
        s,
    ):
        if m.start() > ptr:
            emit_text(s[ptr : m.start()])
        ptr = m.end()
        tok = m.group(0)
        if tok.startswith("\x1b[") and tok.endswith("m"):
            apply([int(x) for x in m.group(1).split(";") if x])
            pending = style_str() or ""
    if ptr < len(s):
        emit_text(s[ptr:])
    return "".join(out)
