"""Window frames: the title bar and border around the terminal, in the style of a desktop.

    [window]
    style = "win95"      # see STYLES
    title = "MS-DOS Prompt"
    buttons = true       # the window's control buttons

A frame only draws chrome. Each style also has a matching prompt and a full preset
(PRESETS) that the web editor offers: the prompt, theme, title and cursor of that
system's own terminal (Terminal.app, MPW's Worksheet, PowerShell, cmd.exe ...).

Every frame is plain SVG shapes and gradients, which GitHub's <img> shows. System
fonts are named in order (Segoe UI, Lucida Grande, Chicago ...) and fall back to
whatever the viewer has, so titles keep roughly the right width either way.
"""

from dataclasses import dataclass
from xml.sax.saxutils import escape

STYLES = {
    "macos": "macOS: traffic lights and a centred title",
    "tahoe": "macOS Tahoe 26: Liquid Glass, rounder and lighter",
    "aqua": "Mac OS X Aqua: glossy gel buttons on pinstripes",
    "platinum": "Mac OS 9 Platinum: a ridged grey title bar",
    "system7": "System 7: black-and-white stripes",
    "win11": "Windows 11: a Mica bar with its controls on the right",
    "win7": "Windows 7 Aero: a glass frame and a red close button",
    "winxp": "Windows XP Luna: the blue title bar",
    "win95": "Windows 95/98: grey bevels and a navy title bar",
    "none": "no title bar, just the rounded box",
}
LABELS = {"macos": "macOS", "tahoe": "macOS Tahoe", "aqua": "Mac OS X Aqua", "platinum": "Mac OS 9", "system7": "System 7",
          "win11": "Windows 11", "win7": "Windows 7", "winxp": "Windows XP", "win95": "Windows 95", "none": "No frame"}

MAC_SANS = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif'
LUCIDA = '"Lucida Grande", "Lucida Sans Unicode", "Helvetica Neue", Helvetica, Arial, sans-serif'
CHICAGO = 'Charcoal, Chicago, ChicagoFLF, Geneva, "Helvetica Neue", Arial, sans-serif'
SEGOE = '"Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'
TREBUCHET = '"Trebuchet MS", "Segoe UI", Tahoma, Verdana, sans-serif'
MS_SANS = '"MS Sans Serif", "Microsoft Sans Serif", Tahoma, Verdana, Arial, sans-serif'


@dataclass(frozen=True)
class Metrics:
    top: float  # the title bar: content starts this far down
    left: float = 0
    right: float = 0
    bottom: float = 0
    title_left: bool = False  # Windows puts the title on the left, after an icon
    buttons_w: float = 0  # room the control buttons take on the title's side of the bar


METRICS = {
    "macos": Metrics(36, buttons_w=75),
    "tahoe": Metrics(42, buttons_w=86),
    "aqua": Metrics(23, buttons_w=72),
    "platinum": Metrics(22, 5, 5, 5, buttons_w=48),
    "system7": Metrics(20, 1, 2, 2, buttons_w=30),
    "win11": Metrics(32, title_left=True, buttons_w=138),
    "win7": Metrics(30, 8, 8, 8, title_left=True, buttons_w=104),
    "winxp": Metrics(30, 4, 4, 4, title_left=True, buttons_w=80),
    "win95": Metrics(24, 4, 4, 4, title_left=True, buttons_w=62),
    "none": Metrics(0),
}

# What each system's own terminal looked like. "prompt" is offered on its own ("use the matching
# prompt"); "preset" also switches the theme, title and cursor.
PRESETS = {
    "macos": {"prompt": "{user}@{host} {cwd} % ", "theme": "terminal-basic", "title": "{user} — -zsh — 80×24",
              "cursor": "block", "user_color": "fg", "cwd_color": "fg"},
    "tahoe": {"prompt": "{user}@{host} {cwd} % ", "theme": "terminal-pro", "title": "{user} — -zsh — 80×24",
              "cursor": "block", "user_color": "fg", "cwd_color": "fg"},
    "aqua": {"prompt": "{host}:{cwd} {user}$ ", "theme": "terminal-basic", "title": "Terminal — bash — 80x24",
             "cursor": "block", "user_color": "fg", "cwd_color": "fg"},
    "platinum": {"prompt": "{cwd} » ", "theme": "classic-mac", "title": "Worksheet", "cursor": "bar",
                 "user_color": "fg", "cwd_color": "fg"},
    "system7": {"prompt": "{cwd} » ", "theme": "classic-mac", "title": "Worksheet", "cursor": "bar",
                "user_color": "fg", "cwd_color": "fg"},
    "win11": {"prompt": "PS C:\\Users\\{user}> ", "theme": "campbell", "title": "Windows PowerShell", "cursor": "bar",
              "user_color": "fg", "cwd_color": "fg"},
    "win7": {"prompt": "PS C:\\Users\\{user}> ", "theme": "powershell", "title": "Windows PowerShell",
             "cursor": "underline", "user_color": "fg", "cwd_color": "fg"},
    "winxp": {"prompt": "C:\\Documents and Settings\\{user}>", "theme": "cmd", "title": "C:\\WINDOWS\\system32\\cmd.exe",
              "cursor": "underline", "user_color": "fg", "cwd_color": "fg"},
    "win95": {"prompt": "C:\\WINDOWS>", "theme": "cmd", "title": "MS-DOS Prompt", "cursor": "underline",
              "user_color": "fg", "cwd_color": "fg"},
}


def metrics(style: str) -> Metrics:
    return METRICS[style]


def min_width(style: str, title: str) -> float:
    """The narrowest window that still fits the title and the buttons."""
    m = METRICS[style]
    if style == "none" or not title:
        return m.buttons_w + m.left + m.right + 40
    chars = len(title) * 7.2
    if m.title_left:
        return m.left + 34 + chars + 16 + m.buttons_w + m.right
    return chars + 2 * m.buttons_w + 20


def _lum(color: str) -> float:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _text(x: float, y: float, title: str, fill: str, font: str, size: float, weight: str = "normal",
          anchor: str = "start", extra: str = "") -> str:
    family = escape(font).replace(chr(34), chr(39))  # double quotes would end the style attribute
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" text-anchor="{anchor}" '
            f'style="font-family:{family};font-size:{size:g}px;font-weight:{weight}"{extra}>{escape(title)}</text>')


def _fit(title: str, room: float, per_char: float = 7.2) -> str:
    """Shorten a title with an ellipsis so it fits `room` px."""
    most = max(int(room / per_char), 0)
    return title if len(title) <= most else (title[:max(most - 1, 0)] + "…" if most > 1 else "")


def draw(style: str, w: float, h: float, title: str, buttons: bool, pal: dict) -> str:
    """The whole window: body, frame and title bar. Content goes on top of it."""
    return _DRAW[style](w, h, title, buttons, pal)


# --- macOS ------------------------------------------------------------------------------------


def _macos(w, h, title, buttons, pal):
    bar = METRICS["macos"].top
    out = [f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{pal["bg"]}" stroke="{pal["border"]}"/>',
           f'<path d="M.5 {bar}V10.5a10 10 0 0 1 10-10h{w - 21}a10 10 0 0 1 10 10V{bar}z" fill="{pal["bar"]}"/>',
           f'<line x1=".5" y1="{bar}" x2="{w - .5}" y2="{bar}" stroke="{pal["border"]}"/>']
    if buttons:
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
            out.append(f'<circle cx="{20 + i * 20}" cy="{bar / 2}" r="6" fill="{c}"/>')
    if title:
        out.append(_text(w / 2, bar / 2 + 4.5, _fit(title, w - 160), pal["dim"], MAC_SANS, 12, anchor="middle"))
    return "".join(out)


def _tahoe(w, h, title, buttons, pal):
    bar = METRICS["tahoe"].top
    dark = _lum(pal["bg"]) < 0.5
    edge = "#ffffff" if dark else "#000000"
    out = ['<defs><linearGradient id="rf-w-glass" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="#fff" stop-opacity="{.09 if dark else .55}"/>'
           f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
           '<linearGradient id="rf-w-sheen" x1="0" y1="0" x2="1" y2="0">'
           '<stop offset="0" stop-color="#fff" stop-opacity=".10"/><stop offset=".3" stop-color="#fff" stop-opacity="0"/>'
           '<stop offset=".7" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".06"/>'
           '</linearGradient></defs>',
           f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="{pal["bg"]}"/>',
           f'<path d="M.5 {bar}V18.5a18 18 0 0 1 18-18h{w - 37}a18 18 0 0 1 18 18V{bar}z" fill="{pal["bar"]}" '
           f'fill-opacity=".72"/>',
           f'<path d="M.5 {bar}V18.5a18 18 0 0 1 18-18h{w - 37}a18 18 0 0 1 18 18V{bar}z" fill="url(#rf-w-glass)"/>',
           f'<path d="M.5 {bar}V18.5a18 18 0 0 1 18-18h{w - 37}a18 18 0 0 1 18 18V{bar}z" fill="url(#rf-w-sheen)"/>',
           f'<line x1="18" y1="{bar}" x2="{w - 18}" y2="{bar}" stroke="{edge}" stroke-opacity=".07"/>',
           f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="18" fill="none" stroke="{edge}" stroke-opacity=".16"/>',
           f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="17" fill="none" stroke="#fff" '
           f'stroke-opacity="{.07 if dark else .6}"/>']
    if buttons:
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
            out.append(f'<circle cx="{24 + i * 22}" cy="{bar / 2}" r="7" fill="{c}" stroke="#000" stroke-opacity=".12" '
                       'stroke-width=".8"/>')
    if title:
        out.append(_text(w / 2, bar / 2 + 4.5, _fit(title, w - 190), pal["fg"], MAC_SANS, 13, "600", "middle",
                         ' fill-opacity=".85"'))
    return "".join(out)


def _gel(cx, cy, r, base, deep, ident):
    return (f'<radialGradient id="rf-w-{ident}" cx=".5" cy=".62" r=".62"><stop offset="0" stop-color="{base}"/>'
            f'<stop offset="1" stop-color="{deep}"/></radialGradient>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#rf-w-{ident})" stroke="#000" stroke-opacity=".42" '
            f'stroke-width=".8"/>'
            f'<ellipse cx="{cx}" cy="{cy - r * .45:.2f}" rx="{r * .62:.2f}" ry="{r * .38:.2f}" fill="url(#rf-w-gloss)"/>')


def _aqua(w, h, title, buttons, pal):
    bar = METRICS["aqua"].top
    out = ['<defs><pattern id="rf-w-pin" width="4" height="2" patternUnits="userSpaceOnUse">'
           '<rect width="4" height="1" fill="#f4f4f4"/><rect y="1" width="4" height="1" fill="#e4e4e4"/></pattern>'
           '<linearGradient id="rf-w-shine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".9"/>'
           '<stop offset=".5" stop-color="#fff" stop-opacity=".15"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
           '</linearGradient>'
           '<linearGradient id="rf-w-gloss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".95"/>'
           '<stop offset="1" stop-color="#fff" stop-opacity=".05"/></linearGradient></defs>',
           f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="5" fill="{pal["bg"]}" stroke="#6e6e6e"/>',
           f'<path d="M.5 {bar}V5.5a5 5 0 0 1 5-5h{w - 11}a5 5 0 0 1 5 5V{bar}z" fill="url(#rf-w-pin)"/>',
           f'<path d="M.5 {bar / 2}V5.5a5 5 0 0 1 5-5h{w - 11}a5 5 0 0 1 5 5V{bar / 2}z" fill="url(#rf-w-shine)"/>',
           f'<line x1=".5" y1="{bar - .5}" x2="{w - .5}" y2="{bar - .5}" stroke="#7d7d7d"/>']
    if buttons:
        out.append(_gel(15, bar / 2, 6.5, "#ff7468", "#c11d10", "red"))
        out.append(_gel(36, bar / 2, 6.5, "#ffd86a", "#d18f00", "yellow"))
        out.append(_gel(57, bar / 2, 6.5, "#9be36b", "#3c8f13", "green"))
    if title:
        out.append(_text(w / 2, bar / 2 + 4.5, _fit(title, w - 150), "#1b1b1b", LUCIDA, 13, anchor="middle"))
    return "".join(out)


def _bevel_box(x, y, s, face="#dddddd", hi="#ffffff", lo="#7b7b7b", line="#262626"):
    return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{face}" stroke="{line}"/>'
            f'<path d="M{x + 1} {y + s - 1}V{y + 1}H{x + s - 1}" fill="none" stroke="{hi}"/>'
            f'<path d="M{x + 1} {y + s - 1}H{x + s - 1}V{y + 1}" fill="none" stroke="{lo}"/>')


def _platinum(w, h, title, buttons, pal):
    m = METRICS["platinum"]
    bar = m.top
    out = [f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" fill="#dddddd" stroke="#262626"/>',
           f'<path d="M1.5 {h - 1.5}V1.5H{w - 1.5}" fill="none" stroke="#fff"/>',
           f'<path d="M1.5 {h - 1.5}H{w - 1.5}V1.5" fill="none" stroke="#9a9a9a"/>',
           f'<rect x="{m.left - .5}" y="{bar - .5}" width="{w - m.left - m.right + 1}" height="{h - bar - m.bottom + 1}" '
           f'fill="{pal["bg"]}" stroke="#555"/>']
    label = _fit(title, w - 2 * 48 - 40, 7.6) if title else ""
    plate = len(label) * 7.6 / 2 + 10 if label else 0
    left_end = 26 if buttons else 6
    right_start = w - (46 if buttons else 6)
    for i in range(6):
        y = 6 + i * 2
        segs = [(left_end, w / 2 - plate), (w / 2 + plate, right_start)] if label else [(left_end, right_start)]
        for a, b in segs:
            if b > a:
                out.append(f'<path d="M{a} {y}.5H{b}" stroke="#fff"/><path d="M{a + 1} {y + 1}.5H{b + 1}" stroke="#a2a2a2"/>')
    if buttons:
        out.append(_bevel_box(8.5, 5.5, 11))
        out.append(_bevel_box(w - 38.5, 5.5, 11) + f'<rect x="{w - 36}" y="8" width="4" height="4" fill="none" stroke="#555"/>')
        out.append(_bevel_box(w - 21.5, 5.5, 11) + f'<path d="M{w - 19} 11.5H{w - 13}" stroke="#555"/>')
    if label:
        out.append(_text(w / 2, 15.5, label, "#000", CHICAGO, 12, "bold", "middle"))
    return "".join(out)


def _system7(w, h, title, buttons, pal):
    bar = METRICS["system7"].top
    out = [f'<rect x="2" y="2" width="{w - 2}" height="{h - 2}" fill="#000"/>',
           f'<rect x=".5" y=".5" width="{w - 2}" height="{h - 2}" fill="{pal["bg"]}" stroke="#000"/>',
           f'<rect x="1" y="1" width="{w - 3}" height="{bar - 1}" fill="#fff"/>',
           f'<line x1="1" y1="{bar - .5}" x2="{w - 1.5}" y2="{bar - .5}" stroke="#000"/>']
    label = _fit(title, w - 2 * 32 - 30, 7.6) if title else ""
    plate = len(label) * 7.6 / 2 + 8 if label else 0
    for i in range(6):
        y = 4.5 + i * 2
        segs = [(3, w / 2 - plate), (w / 2 + plate, w - 4.5)] if label else [(3, w - 4.5)]
        for a, b in segs:
            out.append(f'<path d="M{a} {y}H{b}" stroke="#000"/>')
    if buttons:
        out.append('<rect x="7" y="3" width="15" height="13" fill="#fff"/><rect x="9.5" y="4.5" width="10" height="10" '
                   'fill="#fff" stroke="#000"/>')
        out.append(f'<rect x="{w - 25}" y="3" width="15" height="13" fill="#fff"/><rect x="{w - 22.5}" y="4.5" width="10" '
                   f'height="10" fill="#fff" stroke="#000"/><path d="M{w - 22.5} 9.5H{w - 17.5}V4.5" fill="none" stroke="#000"/>')
    if label:
        out.append(_text(w / 2, 14.5, label, "#000", CHICAGO, 12, "bold", "middle"))
    return "".join(out)


# --- Windows ----------------------------------------------------------------------------------


def _prompt_icon(x, y, s, bg="#012456", fg="#fff", rx=2):
    """A small terminal-app icon: a dark tile with a >_ prompt."""
    k = s / 16
    return (f'<g transform="translate({x} {y}) scale({k:.3f})"><rect width="16" height="16" rx="{rx}" fill="{bg}"/>'
            f'<path d="M3.5 4.5l3.5 3.5-3.5 3.5M8 12h4.5" fill="none" stroke="{fg}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></g>')


def _win11(w, h, title, buttons, pal):
    bar = METRICS["win11"].top
    dark = _lum(pal["bar"]) < 0.5
    glyph = "#ffffff" if dark else "#1b1b1b"
    out = [f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8" fill="{pal["bg"]}"/>',
           f'<path d="M.5 {bar}V8.5a8 8 0 0 1 8-8h{w - 17}a8 8 0 0 1 8 8V{bar}z" fill="{pal["bar"]}"/>',
           f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8" fill="none" stroke="{pal["border"]}"/>',
           _prompt_icon(12, 8, 16, rx=3)]
    if title:
        out.append(_text(38, 20.5, _fit(title, w - 38 - 150), glyph, SEGOE, 12, extra=' fill-opacity=".9"'))
    if buttons:
        x = w - 138
        out.append(f'<path d="M{x + 18} 16.5H{x + 28}" stroke="{glyph}"/>')
        out.append(f'<rect x="{x + 64.5}" y="11.5" width="9" height="9" rx="1.5" fill="none" stroke="{glyph}"/>')
        out.append(f'<path d="M{x + 110} 11l10 10M{x + 120} 11l-10 10" stroke="{glyph}"/>')
    return "".join(out)


def _win7(w, h, title, buttons, pal):
    m = METRICS["win7"]
    out = ['<defs><linearGradient id="rf-w-aero" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="#c3d9f1"/><stop offset=".12" stop-color="#a9c7e8"/><stop offset=".6" '
           'stop-color="#8fb3dd"/>'
           '<stop offset="1" stop-color="#7ea5d6"/></linearGradient>'
           '<linearGradient id="rf-w-streak" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
           '<stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
           '</linearGradient>'
           '<linearGradient id="rf-w-btn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f2f6fb"/>'
           '<stop offset=".45" stop-color="#d7e4f3"/><stop offset=".5" stop-color="#bccfe7"/><stop offset="1" '
           'stop-color="#d3e2f5"/>'
           '</linearGradient>'
           '<linearGradient id="rf-w-close" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9a99a"/>'
           '<stop offset=".45" stop-color="#d9775f"/><stop offset=".5" stop-color="#c3401f"/><stop offset="1" '
           'stop-color="#d9603a"/>'
           '</linearGradient>'
           '<filter id="rf-w-glow" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="2.5"/></filter>'
           '</defs>',
           f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="7" fill="url(#rf-w-aero)" stroke="#3a5a84"/>',
           f'<path d="M{w * .18:.0f} 1h70l-{40 + h * .05:.0f} {h - 2}h-70z" fill="url(#rf-w-streak)"/>',
           f'<path d="M{w * .62:.0f} 1h40l-{30 + h * .05:.0f} {h - 2}h-40z" fill="url(#rf-w-streak)" opacity=".7"/>',
           f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="6" fill="none" stroke="#fff" stroke-opacity=".55"/>',
           f'<rect x="{m.left - .5}" y="{m.top - .5}" width="{w - m.left - m.right + 1}" height="{h - m.top - m.bottom + 1}" '
           f'fill="{pal["bg"]}" stroke="#5b7aa3"/>',
           _prompt_icon(9, 7, 16, rx=2)]
    if title:
        label = _fit(title, w - 34 - 120)
        out.append(f'<g filter="url(#rf-w-glow)">'
                   f'<rect x="30" y="9" width="{len(label) * 6.6 + 8:.0f}" height="12" rx="6" fill="#fff" opacity=".85"/></g>')
        out.append(_text(34, 19.5, label, "#000", SEGOE, 12))
    if buttons:
        x = w - m.right - 2 - 97
        out.append(f'<path d="M{x} 1v14a4 4 0 0 0 4 4h93a4 4 0 0 0 4-4V1z" fill="#000" fill-opacity=".25"/>')
        out.append(f'<path d="M{x} 1v14a4 4 0 0 0 4 4h22V1z" fill="url(#rf-w-btn)" stroke="#5d7aa2" stroke-width=".8"/>')
        out.append(f'<rect x="{x + 27}" y="1" width="26" height="18" fill="url(#rf-w-btn)" stroke="#5d7aa2" stroke-width=".8"/>')
        cx = x + 54
        out.append(f'<path d="M{cx} 1v18h39a4 4 0 0 0 4-4V1z" fill="url(#rf-w-close)" stroke="#7c2a17" stroke-width=".8"/>')
        out.append(f'<path d="M{x + 10} 13.5h8" stroke="#1d3557" stroke-width="2"/>')
        out.append(f'<rect x="{x + 36.5}" y="6.5" width="9" height="7" fill="none" stroke="#1d3557" stroke-width="1.6"/>')
        out.append(f'<path d="M{cx + 15} 6l8 7M{cx + 23} 6l-8 7" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>')
    return "".join(out)


def _xp_button(x, y, close=False):
    grad = "rf-w-xpclose" if close else "rf-w-xpbtn"
    return f'<rect x="{x}" y="{y}" width="21" height="21" rx="3" fill="url(#{grad})" stroke="#fff" stroke-width="1"/>'


def _winxp(w, h, title, buttons, pal):
    m = METRICS["winxp"]
    out = ['<defs><linearGradient id="rf-w-luna" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="#0997ff"/><stop offset=".08" stop-color="#0053ee"/><stop offset=".4" '
           'stop-color="#0050ee"/>'
           '<stop offset=".86" stop-color="#0062ef"/><stop offset=".94" stop-color="#0042b8"/><stop offset="1" '
           'stop-color="#003092"/>'
           '</linearGradient>'
           '<linearGradient id="rf-w-xpbtn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7fb1fa"/>'
           '<stop offset=".5" stop-color="#2a6ef0"/><stop offset="1" stop-color="#1c4fd1"/></linearGradient>'
           '<linearGradient id="rf-w-xpclose" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f19a7f"/>'
           '<stop offset=".5" stop-color="#e2532c"/><stop offset="1" stop-color="#b8300f"/></linearGradient></defs>',
           f'<path d="M0 {h}V8a8 8 0 0 1 8-8h{w - 16}a8 8 0 0 1 8 8V{h}z" fill="#0831d9"/>',
           f'<path d="M0 {m.top}V8a8 8 0 0 1 8-8h{w - 16}a8 8 0 0 1 8 8V{m.top}z" fill="url(#rf-w-luna)"/>',
           f'<path d="M1 8a7 7 0 0 1 7-7h{w - 16}a7 7 0 0 1 7 7" fill="none" stroke="#fff" stroke-opacity=".35"/>',
           f'<rect x="{m.left}" y="{m.top}" width="{w - m.left - m.right}" height="{h - m.top - m.bottom}" fill="{pal["bg"]}"/>',
           _prompt_icon(7, 7, 16, bg="#000", rx=1)]
    if title:
        label = _fit(title, w - 30 - 100, 7.8)
        out.append(_text(31, 20, label, "#0a1883", TREBUCHET, 13, "bold"))
        out.append(_text(30, 19, label, "#fff", TREBUCHET, 13, "bold"))
    if buttons:
        x = w - m.right - 4 - 69
        out.append(_xp_button(x, 5) + f'<path d="M{x + 5} 16.5h7" stroke="#fff" stroke-width="3"/>')
        out.append(_xp_button(x + 23, 5) + f'<rect x="{x + 28.5}" y="10.5" width="10" height="10" fill="none" stroke="#fff" '
                   f'stroke-width="1"/><path d="M{x + 28.5} 11.5h10" stroke="#fff" stroke-width="2"/>')
        out.append(_xp_button(x + 46, 5, True) + f'<path d="M{x + 51.5} 10.5l10 10M{x + 61.5} 10.5l-10 10" stroke="#fff" '
                   f'stroke-width="2.2"/>')
    return "".join(out)


def _w95_button(x, y):
    return (f'<rect x="{x}" y="{y}" width="16" height="14" fill="#c0c0c0"/>'
            f'<path d="M{x}.5 {y + 13}V{y}.5H{x + 15}" fill="none" stroke="#fff"/>'
            f'<path d="M{x} {y + 13}.5H{x + 15}.5V{y}" fill="none" stroke="#000"/>'
            f'<path d="M{x + 1} {y + 12}.5H{x + 14}.5V{y + 1}" fill="none" stroke="#808080"/>')


def _win95(w, h, title, buttons, pal):
    m = METRICS["win95"]
    out = ['<defs><linearGradient id="rf-w-w98" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000080"/>'
           '<stop offset="1" stop-color="#1084d0"/></linearGradient></defs>',
           f'<rect width="{w}" height="{h}" fill="#c0c0c0"/>',
           f'<path d="M.5 {h - 1}V.5H{w - 1}" fill="none" stroke="#dfdfdf"/>',
           f'<path d="M1.5 {h - 2}V1.5H{w - 2}" fill="none" stroke="#fff"/>',
           f'<path d="M0 {h - .5}H{w - .5}V0" fill="none" stroke="#000"/>',
           f'<path d="M1 {h - 1.5}H{w - 1.5}V1" fill="none" stroke="#808080"/>',
           f'<rect x="3" y="3" width="{w - 6}" height="18" fill="url(#rf-w-w98)"/>',
           f'<rect x="{m.left}" y="{m.top}" width="{w - m.left - m.right}" height="{h - m.top - m.bottom}" fill="{pal["bg"]}"/>',
           _prompt_icon(5, 4, 16, bg="#000", rx=0)]
    if title:
        out.append(_text(24, 16, _fit(title, w - 24 - 70, 6.6), "#fff", MS_SANS, 11, "bold"))
    if buttons:
        x = int(w) - 6 - 50
        out.append(_w95_button(x, 5) + f'<rect x="{x + 4}" y="14" width="6" height="2" fill="#000"/>')
        out.append(_w95_button(x + 16, 5) + f'<rect x="{x + 19.5}" y="7.5" width="8" height="7" fill="none" stroke="#000"/>'
                   f'<path d="M{x + 19.5} 8.5h8" stroke="#000"/>')
        out.append(_w95_button(x + 34, 5) + f'<path d="M{x + 38} 8l7 6M{x + 45} 8l-7 6" stroke="#000" stroke-width="1.6"/>')
    return "".join(out)


def _none(w, h, title, buttons, pal):
    return f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{pal["bg"]}" stroke="{pal["border"]}"/>'


_DRAW = {"macos": _macos, "tahoe": _tahoe, "aqua": _aqua, "platinum": _platinum, "system7": _system7,
         "win11": _win11, "win7": _win7, "winxp": _winxp, "win95": _win95, "none": _none}


def thumbnail(style: str, pal: dict, title: str = "user@host: ~") -> str:
    """A small picture of a frame around a few lines of text (the web editor's style picker)."""
    m = METRICS[style]
    w, inner_h = 260, 74
    h = m.top + inner_h + m.bottom
    x0, y0 = m.left + 14, m.top + 22
    lines = "".join(f'<rect x="{x0}" y="{y0 + i * 14 - 7}" width="{wd}" height="6" rx="2" fill="{c}"/>'
                    for i, (wd, c) in enumerate([(70, pal["green"]), (120, pal["fg"]), (96, pal["dim"]), (8, pal["fg"])]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h:g}" viewBox="0 0 {w} {h:g}">'
            f'{draw(style, w, h, title, True, pal)}{lines}</svg>')
