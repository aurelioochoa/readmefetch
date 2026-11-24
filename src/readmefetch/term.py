"""Render the same output in a terminal with 24-bit ANSI colour (or plain text)."""

from .logos import Grid
from .themes import hex_rgb, resolve

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


def render(cfg, rows: list, logo, pal: dict, color: bool = True) -> str:
    still = logo.still() if logo else []
    width = max((len(r) for r in still), default=0)
    art = grid_lines(still, width, pal, color)
    key = resolve(logo.accent, pal) if logo else pal["accent"]
    paint = (lambda hx, s, bold=False: f"{fg(hx, bold)}{s}{RESET}") if color else (lambda hx, s, bold=False: s)

    user, _, host = cfg.title.partition("@")
    info = [paint(key, user, True) + paint(pal["fg"], "@") + paint(key, host, True), paint(pal["dim"], "-" * len(cfg.title))]
    for r in rows:
        if r is None:
            info.append("")
        elif r[0]:
            info.append(paint(key, r[0], True) + paint(pal["fg"], ": " + r[1]))
        else:
            info.append(paint(pal["fg"], r[1]))
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
