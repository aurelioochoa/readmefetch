"""Info lines with more than text: icons and the GitHub visuals.

A line is split into spans, each a whole number of character cells wide:

    Text     plain text (colour None: the colour of the key or value it sits in)
    Icon     :name: from the icon catalogue, two cells wide
    Dot      a coloured dot, one cell (the language legend)
    Bars     {graph}: one bar per week of contributions
    Heat     {heatmap}: GitHub's grid of days, 7 squares tall, drawn over 4 lines
    LangBar  {langbar}: a bar split by language share

The SVG renderer draws each span as shapes on the character grid; the terminal
renderer prints block characters (and Nerd Font glyphs when asked to).
"""

import datetime as dt
import math
import re
from dataclasses import dataclass, field

from . import icons as icon_mod

HEAT_ROWS = 4  # text lines a heatmap covers (7 squares of 11 px fit in 4 lines of 20 px)
# GitHub's contribution greens: empty, then levels 1-4.
GREENS_DARK = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
GREENS_LIGHT = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]


@dataclass
class Text:
    text: str
    color: str | None = None

    @property
    def width(self) -> int:
        return len(self.text)


@dataclass
class Icon:
    key: str
    color: str | None = None
    width: int = 2


@dataclass
class Dot:
    color: str
    width: int = 1


@dataclass
class Bars:
    counts: list[int]  # one per week, oldest first
    levels: list[int]  # 0-4
    colors: list[str]

    @property
    def width(self) -> int:
        return len(self.counts)


@dataclass
class Heat:
    weeks: list[list[int]]  # each week: up to 7 levels (Sunday first); -1 = no such day yet
    colors: list[str]
    cell: float = 11.0  # px per square, gap included

    @property
    def width(self) -> int:
        return math.ceil(len(self.weeks) * self.cell / 8.4)


@dataclass
class LangBar:
    parts: list[tuple[str, float, str]]  # (name, share 0-1, colour)
    width: int = 30


Span = Text | Icon | Dot | Bars | Heat | LangBar


@dataclass
class Visuals:
    """Settings for the GitHub visuals ([metrics] in the config)."""

    weeks: int = 26  # weeks in {graph} and {heatmap}
    languages: int = 4  # languages named in {languages} and split out in {langbar}; the rest are "Other"
    bar_width: int = 30  # cells in {langbar}
    colors: list[str] = field(default_factory=list)  # 5 colours: empty, then levels 1-4; default GitHub's greens
    exclude: list[str] = field(default_factory=list)  # languages to leave out, e.g. ["HTML", "Jupyter Notebook"]


def width(spans) -> int:
    if isinstance(spans, str):
        return len(spans)
    return sum(s.width for s in spans)


def plain(spans) -> str:
    """Words for alt text and the SVG's <desc>."""
    if isinstance(spans, str):
        return spans
    out = []
    for s in spans:
        if isinstance(s, Text):
            out.append(s.text)
        elif isinstance(s, Bars):
            out.append(f"a graph of {sum(s.counts)} contributions over {len(s.counts)} weeks")
        elif isinstance(s, Heat):
            out.append(f"a contribution heatmap of {len(s.weeks)} weeks")
        elif isinstance(s, LangBar):
            out.append(", ".join(f"{n} {p * 100:.0f}%" for n, p, _ in s.parts))
    return re.sub(r"\s+", " ", "".join(out)).strip()


def is_plain(spans) -> bool:
    return all(isinstance(s, Text) and s.color is None for s in spans)


# --- building the visuals from GitHub numbers --------------------------------------------------


def greens(pal: dict, custom: list[str] | None = None) -> list[str]:
    if custom and len(custom) == 5:
        return list(custom)
    bg = pal.get("bg", "#000000").lstrip("#")
    r, g, b = (int(bg[i:i + 2], 16) for i in (0, 2, 4)) if len(bg) == 6 else (0, 0, 0)
    light = 0.299 * r + 0.587 * g + 0.114 * b > 140
    return list(GREENS_LIGHT if light else GREENS_DARK)


def _weeks(days: list[tuple[str, int, int]], count: int) -> list[list[tuple[int, int]]]:
    """Days grouped into GitHub's Sunday-first weeks, the last `count` of them: [[(count, level)]]."""
    weeks: list[list[tuple[int, int]]] = []
    for date, n, level in days:
        d = dt.date.fromisoformat(date)
        if not weeks or (d.weekday() + 1) % 7 == 0:
            weeks.append([])
        weeks[-1].append((n, level))
    return weeks[-count:]


def bars(days, settings: Visuals, colors: list[str]) -> Bars:
    weeks = _weeks(days, settings.weeks)
    counts = [sum(n for n, _ in w) for w in weeks] or [0] * settings.weeks
    top = max(counts) or 1
    levels = [0 if not c else min(4, 1 + int(4 * c / (top + 1))) for c in counts]
    return Bars(counts, levels, colors)


def heat(days, settings: Visuals, colors: list[str]) -> Heat:
    weeks = _weeks(days, settings.weeks) or [[(0, 0)] * 7 for _ in range(settings.weeks)]
    grid = []
    for i, w in enumerate(weeks):
        levels = [lv for _, lv in w]
        if i == 0 and len(levels) < 7:  # a partial first week starts later in the week
            levels = [-1] * (7 - len(levels)) + levels
        grid.append(levels + [-1] * (7 - len(levels)))
    return Heat(grid, colors)


def language_parts(langs, settings: Visuals) -> list[tuple[str, float, str]]:
    langs = [x for x in langs if x[0] not in set(settings.exclude)]
    total = sum(size for _, size, _ in langs) or 1
    top = [(name, size / total, color or "#8b949e") for name, size, color in langs[:settings.languages]]
    rest = 1 - sum(p for _, p, _ in top)
    if len(langs) > settings.languages and rest > 0.0005:
        top.append(("Other", rest, "#8b949e"))
    return top


def legend(parts) -> list[Span]:
    out: list[Span] = []
    for i, (name, share, color) in enumerate(parts):
        if i:
            out.append(Text("  "))
        pctg = f"{share * 100:.1f}".rstrip("0").rstrip(".")
        out += [Dot(color), Text(f" {name} {pctg}%")]
    return out


def visual_values(stats: dict, settings: Visuals, pal: dict) -> dict:
    """Placeholder values that are spans, from the raw numbers stats.fetch() returns."""
    out: dict = {}
    colors = greens(pal, settings.colors)
    if "calendar" in stats:
        days = stats["calendar"] or []
        out["graph"] = [bars(days, settings, colors)]
        out["heatmap"] = [heat(days, settings, colors)]
    if "languages" in stats:
        parts = language_parts(stats["languages"] or [], settings)
        out["top_language"] = parts[0][0] if parts else "?"
        out["languages"] = legend(parts) if parts else [Text("?")]
        out["langbar"] = [LangBar(parts, settings.bar_width)] if parts else [Text("?")]
    return out


# --- parsing a line ----------------------------------------------------------------------------

PLACEHOLDER = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")


def parse(line: str, values: dict) -> list[Span]:
    """A config line -> spans: placeholders expanded, :icons: drawn, {{ }} unescaped."""
    out: list[Span] = []
    pos = 0
    for m in PLACEHOLDER.finditer(line):
        out += _text(line[pos:m.start()])
        v = values.get(m.group(1), m.group(0))
        if isinstance(v, list):
            out += v
        else:
            out.append(Text(_number(v)))
        pos = m.end()
    out += _text(line[pos:])
    merged: list[Span] = []
    for s in out:
        if isinstance(s, Text) and merged and isinstance(merged[-1], Text) and merged[-1].color == s.color:
            merged[-1] = Text(merged[-1].text + s.text, s.color)
        elif not (isinstance(s, Text) and not s.text):
            merged.append(s)
    return merged


def _number(v) -> str:
    return str(v)


def _text(text: str) -> list[Span]:
    text = text.replace("{{", "{").replace("}}", "}")
    out: list[Span] = []
    pos = 0
    for m in icon_mod.SHORTCODE.finditer(text):
        key = icon_mod.lookup(m.group(1))
        if not key:
            continue
        out.append(Text(text[pos:m.start()]))
        out.append(Icon(key))
        pos = m.end()
    out.append(Text(text[pos:]))
    return out


def shortcodes(line: str) -> list[str]:
    """Every :name: in a line that looks meant as an icon but isn't one (for error messages)."""
    return [m.group(1) for m in icon_mod.SHORTCODE.finditer(line)
            if m.group(1).startswith("nf-") and not icon_mod.lookup(m.group(1))]


def split_key(spans: list[Span]) -> tuple[list[Span], list[Span]] | None:
    """'Key: value' -> (key spans, value spans) when the first ': ' comes before any visual."""
    for i, s in enumerate(spans):
        if isinstance(s, Text) and ": " in s.text:
            head, _, tail = s.text.partition(": ")
            key = spans[:i] + ([Text(head)] if head else [])
            if not head and not key:
                return None
            value = ([Text(tail)] if tail else []) + spans[i + 1:]
            return key, value
        if not isinstance(s, (Text, Icon)):
            return None
    return None
