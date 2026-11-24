"""Render the same output in a terminal with 24-bit ANSI colour (or plain text).

Icons print as their Nerd Font glyph with `nerd_font=True`, and are left out otherwise
(most terminal fonts don't have them). The GitHub visuals print as block characters.
"""

import re

from . import icons, rich
from .logos import Grid
from .themes import hex_rgb, resolve

SPARK = " ▁▂▃▄▅▆▇█"

RESET = "\x1b[0m"


def fg(hex_color: str, bold: bool = False) -> str:
    r, g, b = hex_rgb(hex_color)
    return f"\x1b[{'1;' if bold else ''}38;2;{r};{g};{b}m"


def bg(hex_color: str) -> str:
    r, g, b = hex_rgb(hex_color)
    return f"\x1b[48;2;{r};{g};{b}m"


def grid_lines(grid: Grid, width: int, pal: dict, color: bool) -> list[str]:
    lines = []
    for row in grid:
        parts, cur = [], None
        for c in range(width):
            cell = row[c] if c < len(row) else None
            if cell is None:
                if cur is not None and color:
                    parts.append(RESET)
                cur = None
                parts.append(" ")
                continue
            ch, col = cell
            hx = resolve(col, pal)
            if color and hx != cur:
                parts.append(fg(hx, bold=True))
            cur = hx
            parts.append(ch)
        if color and cur is not None:
            parts.append(RESET)
        lines.append("".join(parts))
    return lines


def spans(content, hx: str, pal: dict, color: bool, bold: bool, nerd_font: bool, below: list) -> str:
    """Text or rich spans in the colour hx. A heatmap adds its lower rows to `below` as (column, text)."""
    paint = (lambda c, s, b=False: f"{fg(c, b)}{s}{RESET}") if color else (lambda c, s, b=False: s)
    if isinstance(content, str):
        return paint(hx, content, bold)
    out, col = [], 0
    for s in content:
        if isinstance(s, rich.Text):
            out.append(paint(resolve(s.color, pal) if s.color else hx, s.text, bold))
            col += len(s.text)
        elif isinstance(s, rich.Icon):
            g = icons.glyph(s.key) if nerd_font else ""
            if g:
                out.append(paint(resolve(s.color, pal) if s.color else hx, g + " "))
                col += 2
        elif isinstance(s, rich.Dot):
            out.append(paint(resolve(s.color, pal), "●"))
            col += 1
        elif isinstance(s, rich.Bars):
            top = max(s.counts) or 1
            for count, level in zip(s.counts, s.levels):
                out.append(paint(s.colors[level], SPARK[max(1, round(8 * count / top)) if count else 1]))
            col += len(s.counts)
        elif isinstance(s, rich.LangBar):
            cells, pos = [], 0.0
            for i, (_, share, c) in enumerate(s.parts):
                end = round((pos + share) * s.width) if i < len(s.parts) - 1 else s.width
                cells.append(paint(resolve(c, pal), "█" * max(end - round(pos * s.width), 0)))
                pos += share
            out.append("".join(cells))
            col += s.width
        elif isinstance(s, rich.Heat):
            rows = []
            for half in range(rich.HEAT_ROWS):
                line = []
                for week in s.weeks:
                    top_lv, low_lv = week[2 * half], (week[2 * half + 1] if 2 * half + 1 < 7 else -1)
                    if not color:
                        line.append("▀" if top_lv > 0 else ("▄" if low_lv > 0 else "·"))
                    elif top_lv < 0 and low_lv < 0:
                        line.append(" ")
                    elif low_lv < 0:
                        line.append(f"{fg(s.colors[top_lv])}▀{RESET}")
                    elif top_lv < 0:
                        line.append(f"{fg(s.colors[low_lv])}▄{RESET}")
                    else:
                        line.append(f"{fg(s.colors[top_lv])}{bg(s.colors[low_lv])}▀{RESET}")
                rows.append("".join(line))
            out.append(rows[0])
            below.extend((col, r) for r in rows[1:])
            col += len(s.weeks)
    return "".join(out)


def visible(text: str) -> int:
    return len(re.sub(r"\x1b\[[0-9;]*m", "", text))


def render(cfg, rows: list, logo, pal: dict, color: bool = True, nerd_font: bool = False) -> str:
    still = logo.still() if logo else []
    width = max((len(r) for r in still), default=0)
    art = grid_lines(still, width, pal, color)
    key = resolve(logo.accent, pal) if logo else pal["accent"]
    paint = (lambda hx, s, bold=False: f"{fg(hx, bold)}{s}{RESET}") if color else (lambda hx, s, bold=False: s)

    user, _, host = cfg.title.partition("@")
    info = [paint(key, user, True) + paint(pal["fg"], "@") + paint(key, host, True), paint(pal["dim"], "-" * len(cfg.title))]
    pending: list = []  # rows of a heatmap still to print: (column, text)
    for r in rows:
        below: list = []
        if r is None:
            if pending:
                c, text = pending.pop(0)
                info.append(" " * c + text)
            else:
                info.append("")
            continue
        if r[0]:
            k = spans(r[0], key, pal, color, True, nerd_font, below)
            v = spans(r[1], pal["fg"], pal, color, False, nerd_font, below)
            line = k + paint(pal["fg"], ": ")
            below = [(visible(line) + c, text) for c, text in below]
            info.append(line + v)
        else:
            info.append(spans(r[1], pal["fg"], pal, color, False, nerd_font, below))
        pending = below
    if cfg.color_blocks:
        names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        info.append("")
        for prefix in ("", "bright-"):
            info.append("".join(f"{bg(pal[prefix + c])}   " for c in names) + RESET if color else "")

    gap = "   " if logo else ""
    lines = []
    for i in range(max(len(art), len(info))):
        left = art[i] if i < len(art) else " " * width
        right = info[i] if i < len(info) else ""
        lines.append((left + gap + right).rstrip() if not color else left + gap + right)
    return "\n".join(lines) + "\n"
