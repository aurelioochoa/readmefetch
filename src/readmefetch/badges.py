"""Badges: small SVG buttons for your README (sites, domains, contact), in several styles.

    [badges]                    # defaults for every badge (optional)
    style = "for-the-badge"
    dir = "badges"

    [[badge]]
    label = "Portfolio"
    message = "example.com"
    link = "https://example.com"
    color = "#00d4ff"           # theme colour name or #hex
    icon = "globe"              # a built-in icon, or the `d` of a 24x24 SVG path (e.g. from simpleicons.org)

Styles: flat, flat-square, plastic, for-the-badge and pill have the familiar shields.io
shapes; terminal is readmefetch's own, a tiny prompt in your theme with a blinking cursor.
Text widths come from a Verdana width table and are pinned with textLength, so a badge
keeps its shape whatever font the viewer has. The built-in icons are original
readmefetch drawings (MIT), not brand logos.
"""

import re
import unicodedata
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from .themes import hex_rgb, resolve

STYLES = {
    "flat": "rounded corners, a soft gradient",
    "flat-square": "square corners, no gradient",
    "plastic": "rounded and glossy",
    "for-the-badge": "tall, square, uppercase and letter-spaced",
    "pill": "fully rounded ends",
    "terminal": "a tiny prompt in your theme, with a blinking cursor",
}
SANS = "Verdana,Geneva,DejaVu Sans,sans-serif"
MONO = 'ui-monospace,SFMono-Regular,Menlo,Consolas,"DejaVu Sans Mono",monospace'

# Verdana 11px advance widths (px) for printable ASCII; anything else counts as an average glyph.
_W = dict(zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [3.87, 4.33, 5.05, 9.0, 7.0, 11.84, 8.0, 2.95, 5.0, 5.0, 7.0, 9.0, 4.0, 5.0, 4.0, 5.0,
     7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 5.0, 5.0, 9.0, 9.0, 9.0, 6.0, 11.0,
     7.52, 7.54, 7.68, 8.48, 6.96, 6.32, 8.53, 8.27, 4.63, 5.0, 7.62, 6.12, 9.27, 8.23, 8.66, 6.63,
     8.66, 7.65, 7.52, 6.78, 8.05, 7.52, 10.87, 7.54, 6.77, 7.54, 5.0, 5.0, 5.0, 9.0, 7.0, 7.0,
     6.61, 6.85, 5.73, 6.85, 6.55, 3.87, 6.85, 6.96, 3.02, 3.79, 6.51, 3.02, 10.7, 6.96, 6.68, 6.85,
     6.85, 4.69, 5.73, 4.33, 6.96, 6.51, 8.98, 6.51, 6.51, 5.78, 6.98, 5.0, 6.98, 9.0],
))

# Original 16x16 line icons (stroked, round caps).
ICONS = {
    "globe": "M14.5 8A6.5 6.5 0 1 1 1.5 8a6.5 6.5 0 0 1 13 0zM1.5 8h13M8 1.5c1.9 1.9 2.8 4.1 2.8 6.5S9.9 12.6 8 14.5"
             "M8 1.5C6.1 3.4 5.2 5.6 5.2 8s.9 4.6 2.8 6.5",
    "mail": "M2 3.5h12v9H2zM2.3 4L8 8.6 13.7 4",
    "link": "M6.8 9.2a2.9 2.9 0 0 0 4.1 0l2.2-2.2a2.9 2.9 0 0 0-4.1-4.1l-.8.8M9.2 6.8a2.9 2.9 0 0 0-4.1 0L2.9 9"
            "a2.9 2.9 0 0 0 4.1 4.1l.8-.8",
    "code": "M5.5 4L2 8l3.5 4M10.5 4L14 8l-3.5 4M9.2 2.8L6.8 13.2",
    "terminal": "M2 2.8h12v10.4H2zM4.6 6l2.2 2-2.2 2M8.4 10.4h3",
    "game": "M5 4.8h6a3.5 3.5 0 0 1 3.5 3.5v1.4a2 2 0 0 1-3.6 1.2L10 9.6H6l-.9 1.3a2 2 0 0 1-3.6-1.2V8.3A3.5 3.5 0 0 1 5 4.8z"
            "M5 6.6v2.2M3.9 7.7h2.2M10.4 7h.1M11.9 8.4h.1",
    "cards": "M3.2 3.4h6.4v9.2H3.2zM9.9 4.3l3 .8-2.1 7.8-1.2-.3M6.4 6.1l1.4 1.9-1.4 1.9L5 8z",
    "tree": "M1.8 6.6c0-1.8 2.8-3.3 6.2-3.3s6.2 1.5 6.2 3.3-2.8 2.3-6.2 2.3-6.2-.5-6.2-2.3zM8 8.9v5.6M8 11.2L5.8 9.1"
            "M8 10.6l2.2-1.7M5.6 14.5h4.8",
    "briefcase": "M2 5.2h12v8.3H2zM5.6 5.2V3h4.8v2.2M2 8.8h12",
    "heart": "M8 13.6S2 10.2 2 6.1a3 3 0 0 1 6-.9 3 3 0 0 1 6 .9c0 4.1-6 7.5-6 7.5z",
    "star": "M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z",
    "home": "M2.3 7.4L8 2.8l5.7 4.6M3.8 6.3v7h8.4v-7M6.6 13.3V9.6h2.8v3.7",
    "rocket": "M8 1.8c2.2 1.6 3.2 4 3 7.2L9.8 11H6.2L5 9c-.2-3.2.8-5.6 3-7.2zM6.2 11l-1.6 2.4M9.8 11l1.6 2.4M8 5.4v.1"
              "M8 12.2v2",
    "book": "M2 3h4.2c1 0 1.8.8 1.8 1.8V13c0-.7-.6-1.3-1.3-1.3H2zM14 3H9.8C8.8 3 8 3.8 8 4.8V13c0-.7.6-1.3 1.3-1.3H14z",
}
ICON_CREDIT = "original readmefetch icons (MIT License)"


@dataclass
class Badge:
    label: str
    message: str = ""
    link: str = ""
    color: str = "accent"
    label_color: str = ""
    icon: str = ""
    style: str = ""
    file: str = ""
    cursor: bool = True  # terminal style: a blinking cursor at the end

    @property
    def text(self) -> str:
        return f"{self.label}: {self.message}" if self.message and self.label else (self.label or self.message)


BADGE_KEYS = {"label", "message", "link", "color", "label_color", "icon", "style", "file", "cursor"}
DEFAULT_KEYS = {"style", "dir", "color", "label_color"}


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "badge"


def parse(items, defaults: dict | None) -> tuple[list[Badge], dict]:
    """[[badge]] entries and the [badges] table -> (badges, defaults with every key)."""
    defaults = dict(defaults or {})
    unknown = set(defaults) - DEFAULT_KEYS
    if unknown:
        raise ValueError(f"unknown setting(s) in [badges]: {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(sorted(DEFAULT_KEYS))}")
    d = {"style": "flat", "dir": "badges", "color": "accent", "label_color": "", **defaults}
    if d["style"] not in STYLES:
        raise ValueError(f"[badges] style: choose one of: {', '.join(STYLES)}")
    folder = str(d["dir"]).replace("\\", "/")
    if not folder.strip() or folder.startswith("/") or re.match(r"^[A-Za-z]:", folder) or ".." in folder.split("/"):
        raise ValueError("[badges] dir: a folder inside your repository, relative to the config file (e.g. \"badges\")")
    out, files = [], set()
    if items is None:
        items = []
    if not isinstance(items, list):
        raise ValueError("badges are written as [[badge]] tables")
    for i, item in enumerate(items, 1):
        where = f"[[badge]] {i}"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be a table")
        unknown = set(item) - BADGE_KEYS
        if unknown:
            raise ValueError(f"{where}: unknown setting(s) {', '.join(sorted(unknown))}; known: {', '.join(sorted(BADGE_KEYS))}")
        b = Badge(label=str(item.get("label", "")), message=str(item.get("message", "")), link=str(item.get("link", "")),
                  color=str(item.get("color") or d["color"]), label_color=str(item.get("label_color") or d["label_color"]),
                  icon=str(item.get("icon", "")), style=str(item.get("style") or d["style"]), file=str(item.get("file", "")),
                  cursor=bool(item.get("cursor", True)))
        if not (b.label.strip() or b.message.strip()):
            raise ValueError(f"{where} needs a label or a message")
        if b.style not in STYLES:
            raise ValueError(f"{where} style: choose one of: {', '.join(STYLES)}")
        if b.icon and b.icon not in ICONS and not re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]+", b.icon):
            raise ValueError(f"{where} icon: use one of {', '.join(ICONS)}, or the d attribute of a 24x24 SVG path")
        b.file = b.file or slug(b.label or b.message) + ".svg"
        if not b.file.endswith(".svg") or "/" in b.file or "\\" in b.file:
            raise ValueError(f"{where} file: a plain file name ending in .svg")
        if b.file in files:
            raise ValueError(f"{where}: two badges would both be written to {b.file}; give one a `file`")
        files.add(b.file)
        out.append(b)
    return out, d


# --- drawing -----------------------------------------------------------------------------


def text_width(text: str, size: float = 11, bold: bool = False, spacing: float = 0) -> float:
    w = 0.0
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0]
        w += _W.get(base, 7.0 if unicodedata.east_asian_width(ch) not in "WF" else 11.0)
    return w * size / 11 * (1.1 if bold else 1) + spacing * len(text)


def _luminance(color: str) -> float:
    def lin(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(color)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _ink(bg: str) -> str:
    """White or near-black text, whichever contrasts more with bg (WCAG contrast ratio)."""
    lum = _luminance(bg)
    return "#ffffff" if (1.05 / (lum + 0.05)) >= ((lum + 0.05) / (_luminance("#1f2328") + 0.05)) else "#1f2328"


def _icon(icon: str, x: float, y: float, size: float, color: str) -> str:
    if icon in ICONS:
        k = size / 16
        return (f'<g transform="translate({x:.1f} {y:.1f}) scale({k:.4f})" fill="none" stroke="{color}" stroke-width="1.6" '
                f'stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[icon]}"/></g>')
    k = size / 24
    return f'<g transform="translate({x:.1f} {y:.1f}) scale({k:.4f})" fill="{color}"><path d={quoteattr(icon)}/></g>'


def render(b: Badge, pal: dict) -> str:
    if b.style == "terminal":
        return _terminal(b, pal)
    tall = b.style == "for-the-badge"
    h = {"for-the-badge": 28, "plastic": 18}.get(b.style, 20)
    size = 10 if tall else 11
    pad = 12 if tall else 6
    spacing = 1.25 if tall else 0
    label = b.label.upper() if tall else b.label
    message = b.message.upper() if tall else b.message
    color = resolve(b.color, pal)
    label_bg = resolve(b.label_color, pal) if b.label_color else ("#555555" if message and label else color)
    icon_size = 14 if tall else 12
    icon_w = icon_size + (5 if label or message else 0) if b.icon else 0

    segments = []  # (text, bg, bold)
    if label:
        segments.append((label, label_bg, False))
    if message:
        segments.append((message, color, tall))
    widths = []
    for i, (text, _, bold) in enumerate(segments):
        widths.append(round(text_width(text, size, bold, spacing) + 2 * pad + (icon_w if i == 0 else 0)))
    if not segments:
        widths = [icon_size + 2 * pad]
    total = sum(widths)
    rx = {"flat": 3, "plastic": 4, "pill": h / 2}.get(b.style, 0)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{h}" role="img" aria-label={quoteattr(b.text)}>',
           f"<title>{escape(b.text)}</title>"]
    if b.style == "flat":
        out.append('<linearGradient id="g" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
                   '<stop offset="1" stop-opacity=".1"/></linearGradient>')
    elif b.style == "plastic":
        out.append('<linearGradient id="g" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".7"/>'
                   '<stop offset=".1" stop-color="#aaa" stop-opacity=".1"/><stop offset=".9" stop-opacity=".3"/>'
                   '<stop offset="1" stop-opacity=".5"/></linearGradient>')
    out.append(f'<clipPath id="r"><rect width="{total}" height="{h}" rx="{rx:g}" fill="#fff"/></clipPath><g clip-path="url(#r)">')
    x = 0
    for (_, bg, _), w in zip(segments, widths):
        out.append(f'<rect x="{x}" width="{w}" height="{h}" fill="{bg}"/>')
        x += w
    if b.style in ("flat", "plastic"):
        out.append(f'<rect width="{total}" height="{h}" fill="url(#g)"/>')
    out.append("</g>")
    if b.icon:
        first_bg = segments[0][1] if segments else color
        out.append(_icon(b.icon, pad, (h - icon_size) / 2, icon_size, _ink(first_bg)))
    shadow = b.style in ("flat", "plastic")
    baseline = {"for-the-badge": 17.5, "plastic": 13}.get(b.style, 14)
    out.append(f'<g text-anchor="middle" font-family="{SANS}" font-size="{size}">')
    x = 0
    for i, ((text, bg, bold), w) in enumerate(zip(segments, widths)):
        inner = w - 2 * pad - (icon_w if i == 0 else 0)
        cx = x + pad + (icon_w if i == 0 else 0) + inner / 2
        tl = text_width(text, size, bold, spacing)
        attrs = (f'x="{cx:.1f}" textLength="{tl:.1f}" lengthAdjust="spacing"'
                 + (' font-weight="bold"' if bold else "") + (f' letter-spacing="{spacing}"' if spacing else ""))
        ink = _ink(bg)
        if shadow and ink == "#ffffff":
            out.append(f'<text {attrs} y="{baseline + 1}" fill="#010101" fill-opacity=".3" aria-hidden="true">'
                       f"{escape(text)}</text>")
        out.append(f'<text {attrs} y="{baseline}" fill="{ink}">{escape(text)}</text>')
        x += w
    out.append("</g></svg>")
    return "".join(out) + "\n"


def _terminal(b: Badge, pal: dict) -> str:
    cw, h, pad = 7.2, 24, 10
    color = resolve(b.color, pal)
    icon_w = 18 if b.icon else 0
    parts = [("$ ", pal["green"], False)]
    if b.label:
        parts.append((b.label + (" " if b.message else ""), color, True))
    if b.message:
        parts.append((b.message, pal["fg"], False))
    chars = sum(len(t) for t, _, _ in parts)
    cursor_w = cw + 2 if b.cursor else 0
    total = round(pad + icon_w + chars * cw + cursor_w + pad)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{h}" role="img" aria-label={quoteattr(b.text)}>',
           f"<title>{escape(b.text)}</title>",
           f'<rect x=".5" y=".5" width="{total - 1}" height="{h - 1}" rx="6" fill="{pal["bg"]}" stroke="{pal["border"]}"/>']
    if b.icon:
        out.append(_icon(b.icon, pad, (h - 13) / 2, 13, color))
    x = pad + icon_w
    out.append(f'<g font-family={quoteattr(MONO)} font-size="12">')
    for text, fill, bold in parts:
        weight = ' font-weight="bold"' if bold else ""
        out.append(f'<text x="{x:.1f}" y="16" fill="{fill}" textLength="{len(text) * cw:.1f}" lengthAdjust="spacing"'
                   f'{weight} xml:space="preserve">{escape(text)}</text>')
        x += len(text) * cw
    out.append("</g>")
    if b.cursor:
        out.append(f'<rect class="c" x="{x + 2:.1f}" y="6" width="{cw:.1f}" height="13" fill="{pal["fg"]}"/>')
        out.append("<style>.c { animation: b 1.1s step-end infinite; } @keyframes b { 50% { opacity: 0; } }"
                   " @media (prefers-reduced-motion: reduce) { .c { animation: none; } }</style>")
    out.append("</svg>")
    return "".join(out) + "\n"


def snippet(badges: list[Badge], directory: str, html: bool = False) -> str:
    """README lines that show the badges, each linked when it has a link."""
    lines = []
    for b in badges:
        src = f"{directory.rstrip('/')}/{b.file}" if directory else b.file
        if html:
            img = f'<img src="{escape(src)}" alt={quoteattr(b.text)}>'
            lines.append(f'<a href="{escape(b.link)}">{img}</a>' if b.link else img)
        else:
            alt = b.text.replace("[", "(").replace("]", ")")
            lines.append(f"[![{alt}]({src})]({b.link})" if b.link else f"![{alt}]({src})")
    return "\n".join(lines) + ("\n" if lines else "")
