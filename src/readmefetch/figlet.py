"""A small FIGlet font reader, for banner logos (your name in big letters).

Implements the FIGfont 2 file format and horizontal "fitting" (letters slide
together until they touch); full smushing rules are not needed for banners.
Fonts live in art/figlet/ with their licences (see CREDITS.md).
"""

from dataclasses import dataclass
from pathlib import Path

FONT_DIR = Path(__file__).parent / "art" / "figlet"
FIGLET_COPYRIGHT = ("FIGlet © 1991-1994 Glenn Chappell & Ian Chai, © 1996-2001 John Cowan, © 2002 Christiaan Keet, "
                    "© 2011 Claudio Matsuoka (BSD-3-Clause)")


@dataclass
class Font:
    name: str
    height: int
    hardblank: str
    chars: dict[str, list[str]]
    comment: str

    @property
    def credit(self) -> str:
        first = self.comment.splitlines()[0].strip() if self.comment else self.name
        if self.name == "tubes":
            return f"FIGlet font Tubes by Phantomwise (CC0 1.0)"
        return f"FIGlet font {self.name}: {first}; {FIGLET_COPYRIGHT}"


def fonts() -> list[str]:
    return sorted(p.stem for p in FONT_DIR.glob("*.flf"))


def load(name: str) -> Font:
    path = FONT_DIR / f"{name}.flf"
    if not path.exists():
        raise ValueError(f"unknown banner font {name!r}; choose one of: {', '.join(fonts())}")
    lines = path.read_text(encoding="utf-8").split("\n")
    header = lines[0].split()
    if not header or not header[0].startswith("flf2a"):
        raise ValueError(f"{path} is not a FIGlet font")
    hardblank = header[0][5]
    height, comments = int(header[1]), int(header[5])
    comment = "\n".join(lines[1:1 + comments])
    chars, i = {}, 1 + comments
    for code in range(32, 127):
        rows = lines[i:i + height]
        if len(rows) < height:
            break
        i += height
        chars[chr(code)] = [_strip_endmark(r) for r in rows]
    return Font(name, height, hardblank, chars, comment)


def _strip_endmark(row: str) -> str:
    row = row.rstrip("\r")
    if not row:
        return row
    mark = row[-1]
    return row.rstrip(mark)


def render(text: str, font: Font) -> list[str]:
    out = [""] * font.height
    for ch in text:
        glyph = font.chars.get(ch) or font.chars.get("?") or [""] * font.height
        width = max(len(r) for r in out)
        out = [r.ljust(width) for r in out]
        g_width = max((len(r) for r in glyph), default=0)
        glyph = [r.ljust(g_width) for r in glyph]
        # slide the glyph left while no visible character would collide
        fit = min(len(o) - len(o.rstrip(" ")) + len(g) - len(g.lstrip(" ")) for o, g in zip(out, glyph))
        fit = min(fit, width, g_width)
        merged = []
        for o, g in zip(out, glyph):
            head, overlap = o[:width - fit], o[width - fit:]
            mix = "".join(b if a == " " else a for a, b in zip(overlap, g[:fit]))
            merged.append(head + mix + g[fit:])
        out = merged
    out = [r.replace(font.hardblank, " ").rstrip() for r in out]
    while out and not out[-1].strip():
        out.pop()
    while out and not out[0].strip():
        out.pop(0)
    return out
