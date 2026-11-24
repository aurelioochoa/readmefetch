"""Logos: readmefetch's own animated art, vendored fastfetch/onefetch art, and custom
logos from the config file.

A logo is a grid of cells, each either empty or (glyph, colour). Colours are theme
names or hex strings, resolved at render time. Animated parts ("layers") are small
grids drawn over the art that cycle through frames; the cells they own are removed
from the base art so frames never overlap stale glyphs.

Custom art uses fastfetch's colour syntax: "$1".."$9" switch to that entry of the
logo's `colors` list and the colour carries on across lines; "$$" is a literal "$".
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import figlet

ART_DIR = Path(__file__).parent / "art"

Cell = tuple[str, str] | None
Grid = list[list[Cell]]

FASTFETCH_CREDIT = (
    "ASCII art from fastfetch (MIT License, © 2021-2023 Linus Dierheimer, © 2022-2026 Carter Li), "
    "much of it originally from neofetch (MIT License, © 2015-2021 Dylan Araps)"
)
ONEFETCH_CREDIT = "ASCII art from onefetch (MIT License, © 2018 Ossama Hjaji)"
ORIGINAL_CREDIT = "original readmefetch art (MIT License)"
ENTERS = ("print", "fly", "fade")


@dataclass
class Layer:
    row: int
    col: int
    frames: list[Grid]
    weights: list[float]
    period: float  # seconds for one pass through all frames


@dataclass
class Logo:
    name: str
    art: Grid
    accent: str  # colour the info keys take while this logo is on screen
    ground: Grid = field(default_factory=list)  # rows under the art that stay put when it flies
    layers: list[Layer] = field(default_factory=list)
    enter: str = "print"  # print: printed line by line; fly: flies in and out; fade
    hover: bool = False  # gentle bobbing while on screen
    source: str = "readmefetch"
    credit: str = ORIGINAL_CREDIT

    @property
    def art_rows(self) -> int:
        bottom = len(self.art)
        for layer in self.layers:
            bottom = max(bottom, layer.row + max(len(f) for f in layer.frames))
        return bottom

    @property
    def height(self) -> int:
        return self.art_rows + len(self.ground)

    @property
    def width(self) -> int:
        w = max((len(r) for r in self.art + self.ground), default=0)
        for layer in self.layers:
            for f in layer.frames:
                w = max(w, layer.col + max((len(r) for r in f), default=0))
        return w

    def base(self) -> Grid:
        """The art minus every cell some layer frame draws on."""
        owned = set()
        for layer in self.layers:
            for f in layer.frames:
                for r, row in enumerate(f):
                    for c, cell in enumerate(row):
                        if cell:
                            owned.add((layer.row + r, layer.col + c))
        return [[None if (r, c) in owned else cell for c, cell in enumerate(row)] for r, row in enumerate(self.art)]

    def still(self) -> Grid:
        """Base art with every layer on its first frame, then the ground: one static picture."""
        grid = [list(row) for row in self.base()]
        grid += [[] for _ in range(self.art_rows - len(grid))]
        for layer in self.layers:
            for r, row in enumerate(layer.frames[0]):
                target = grid[layer.row + r]
                for c, cell in enumerate(row):
                    if cell:
                        col = layer.col + c
                        target.extend([None] * (col + 1 - len(target)))
                        target[col] = cell
        return grid + [list(row) for row in self.ground]


# --- parsing -------------------------------------------------------------------------


def parse_dollar(text: str, colors: list[str], default: str = "fg") -> Grid:
    """fastfetch syntax: $1-$9 pick colors[n-1] (sticky across lines), $$ is a literal $."""
    current = colors[0] if colors else default
    grid: Grid = []
    for line in text.expandtabs(4).split("\n"):
        row: list[Cell] = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "$" and i + 1 < len(line):
                nxt = line[i + 1]
                if nxt == "$":
                    row.append(("$", current))
                    i += 2
                    continue
                if nxt in "123456789":
                    idx = int(nxt) - 1
                    if idx < len(colors):  # fastfetch drops placeholders that have no colour
                        current = colors[idx]
                    i += 2
                    continue
            row.append(None if ch == " " else (ch, current))
            i += 1
        grid.append(row)
    return _trim(grid)


def parse_braces(text: str, colors: list[str], default: str = "fg") -> Grid:
    """onefetch syntax: {0}, {1}, ... pick colors[n] (sticky across lines)."""
    return parse_dollar(re.sub(r"\{(\d)\}", lambda m: f"${int(m.group(1)) + 1}", text.replace("$", "$$")), colors, default)


def paint(lines: list[str], color) -> Grid:
    """Plain text lines + color(row, col, glyph) -> grid."""
    return [[None if ch == " " else (ch, color(r, c, ch)) for c, ch in enumerate(line)] for r, line in enumerate(lines)]


def _trim(grid: Grid) -> Grid:
    for row in grid:
        while row and row[-1] is None:
            row.pop()
    while grid and not grid[-1]:
        grid.pop()
    return grid


# --- readmefetch originals -----------------------------------------------------------


def _drone(ctx: dict) -> Logo:
    """Top-down spraying drone (quadcopter) over a crop field."""
    a, b = (str(ctx.get("initials", "")) + "  ")[:2]
    art = [
        r" .-------.             .-------. ",
        r"(         )           (         )",
        r" '---+---'             '---+---' ",
        r"      \     .-------.     /      ",
        r"       \   /         \   /       ",
        r"        \ |           | /        ",
        r"         \|   .---.   |/         ",
        rf"          |  ( {a} {b} )  |          ",
        r"         /|   '---'   |\         ",
        r"        / |           | \        ",
        r"       /   \         /   \       ",
        r"      /     '-------'     \      ",
        r" .---+---.             .---+---. ",
        r"(         )           (         )",
        r" '-------'             '-------' ",
    ]

    def body(r, c, ch):
        if r in (0, 2, 12, 14):
            return "accent" if ch == "+" else "dim"
        if r in (1, 13):
            return {0: "red", 32: "green"}.get(c, "dim")  # navigation lights: red left, green right
        if 6 <= r <= 8 and 13 <= c <= 19:
            return "bright-white"
        return "accent"

    def blades(s):
        line = s + " " * 13 + s
        return paint([line], lambda r, c, ch: "bright-white" if ch == "O" else "white")

    spin = [blades("----O----"), blades("--- O ---"), blades(" -- O -- ")]
    spray_rows = [r" ' . ' . '             ' . ' . ' ", r" . ' . ' .             . ' . ' . "]
    spray = [
        paint(spray_rows, lambda r, c, ch: "blue"),
        paint(spray_rows[::-1], lambda r, c, ch: "bright-blue"),
    ]
    crops = paint(["\\|/" * 11], lambda r, c, ch: "green" if (c // 3) % 2 else "bright-green")
    return Logo(
        name="drone",
        art=paint(art, body),
        accent="accent",
        ground=crops,
        layers=[
            Layer(1, 1, spin, [1, 1, 1], 0.36),
            Layer(13, 1, spin, [1, 1, 1], 0.36),
            Layer(15, 0, spray, [1, 1], 0.5),
        ],
        enter="fly",
        hover=True,
    )


def _pot(ctx: dict) -> Logo:
    """A steaming pot on a stove."""
    art = [
        "", "", "",
        r"              .-.              ",
        r"      .------'   '------.      ",
        r"     (___________________)     ",
        r"      |                 |      ",
        r"    __|                 |__    ",
        r"   (__|  ~ ~ ~ ~ ~ ~ ~  |__)   ",
        r"      |                 |      ",
        r"      |                 |      ",
        r"       \_______________/       ",
        r"  ===========================  ",
    ]

    def body(r, c, ch):
        if r == 3:
            return "bright-yellow"
        if r in (4, 5):
            return "bright-white"
        if r == 12:
            return "bright-black"
        if ch == "~":
            return "bright-red"
        if r in (7, 8) and (c < 7 or c > 23):
            return "bright-black"  # handles
        return "white"

    steam = [
        paint([" (   )   ( ", "  )   (   )", " (   )   ( "], lambda r, c, ch: "dim"),
        paint([" )   (   ) ", "  (   )   (", " )   (   ) "], lambda r, c, ch: "bright-black"),
    ]
    tops = [r"       /\   /\   /\   /\       ", r"       )(   )(   )(   )(       ", r"       /\   )(   /\   )(       "]
    base = r"      (  ) (  ) (  ) (  )      "
    hues = [("bright-yellow", "red"), ("red", "yellow"), ("yellow", "bright-red")]
    flames = [paint([t, base], lambda r, c, ch, h=h: h[r]) for t, h in zip(tops, hues)]
    return Logo(
        name="pot",
        art=paint(art, body),
        accent="bright-red",
        layers=[Layer(0, 10, steam, [1, 1], 1.2), Layer(13, 0, flames, [1, 1, 1], 0.45)],
    )


def _tux(ctx: dict) -> Logo:
    """fastfetch's Linux logo (Tux), with blinking eyes added by readmefetch."""
    logo = _fastfetch("linux")
    eye = logo.art[2][9][1]
    logo.name = "tux"
    logo.layers = [Layer(2, 9, [parse_dollar("$1O O", [eye]), parse_dollar("$1- -", [eye])], [30, 1], 4.0)]
    logo.credit = FASTFETCH_CREDIT + "; blinking eyes added by readmefetch"
    return logo


def _banner(ctx: dict) -> Logo:
    """Your name (or any text) in a FIGlet font, with a colour wave rolling across it."""
    spec = ctx.get("banner") or {}
    font = figlet.load(str(spec.get("font", "slant")))
    lines = figlet.render(str(spec.get("text") or ctx.get("user") or "hello"), font)
    colors = spec.get("colors") or ["bright-cyan", "bright-blue", "bright-magenta", "magenta", "bright-blue"]
    colors = [colors] if isinstance(colors, str) else list(colors)

    def tint(shift):
        return lambda r, c, ch: colors[((c + 2 * r) // 6 + shift) % len(colors)]

    art = paint(lines, tint(0))
    layers = []
    if spec.get("wave", True) and len(colors) > 1:
        layers = [Layer(0, 0, [paint(lines, tint(-i)) for i in range(len(colors))], [1] * len(colors), 0.35 * len(colors))]
    return Logo(name="banner", art=art, accent=colors[0], layers=layers, credit=font.credit + "; colours by readmefetch")


ORIGINALS = {"drone": _drone, "pot": _pot, "tux": _tux}


# --- vendored art --------------------------------------------------------------------


def _index(source: str) -> dict:
    return json.loads((ART_DIR / source / "index.json").read_text(encoding="utf-8"))["logos"]


CANDYBOX2_LICENSE = "CC BY-SA 3.0, https://creativecommons.org/licenses/by-sa/3.0/"


def _candybox2(name: str) -> tuple[str, list[str]]:
    meta = _index("candybox2")[name]
    lines = (ART_DIR / "candybox2" / meta["file"]).read_text(encoding="utf-8").split("\n")[1:]  # drop "@author"
    while lines and not lines[-1].strip():
        lines.pop()
    return meta["author"], [line.rstrip() for line in lines]


def _cb2_credit(author: str, changes: str) -> str:
    return f"ASCII art by {author} from Candy Box 2 ({CANDYBOX2_LICENSE}); {changes} by readmefetch"


def _cauldron(ctx: dict) -> Logo:
    """dixsept's cauldron from Candy Box 2, boiling over a flickering fire."""
    author, lines = _candybox2("cauldron")
    top = 2  # rows added above the rim for the bubbles
    art_lines = [""] * top + lines
    fire = [i for i, line in enumerate(art_lines) if line and set(line) <= {"W", "M"}]

    def body(r, c, ch):
        if r in (top, top + 1):
            return "bright-white"
        if ch == "¨":
            return "bright-black"
        if r >= top + 13:
            return "bright-black"  # legs
        return "white"

    hues = ["red", "yellow", "bright-yellow", "bright-red"]
    flames = [paint([art_lines[r] for r in fire], lambda r, c, ch, i=i: hues[(c // 3 + r + i) % len(hues)]) for i in range(4)]
    bubbles = [
        paint(["   o      O    .   ", "      .     o      "], lambda r, c, ch: "bright-green"),
        paint(["  .    o      O    ", "    O     .     o  "], lambda r, c, ch: "green"),
        paint(["     O    .     o  ", "  o     O     .    "], lambda r, c, ch: "bright-green"),
    ]
    return Logo(
        name="cauldron",
        art=paint(art_lines, body),
        accent="bright-green",
        layers=[Layer(fire[0], 0, flames, [1] * 4, 0.6), Layer(0, 12, bubbles, [1, 1, 1], 1.2)],
        source="candybox2",
        credit=_cb2_credit(author, "colours, bubbles and fire animation added"),
    )


def _computer(ctx: dict) -> Logo:
    """aniwey's computer from Candy Box 2 (just the monitor), with a session typed on screen."""
    author, lines = _candybox2("computer")
    monitor = [line[:40].rstrip() for line in lines[4:24]]

    def body(r, c, ch):
        if 2 <= r <= 13 and 2 <= c <= 37:
            return "bright-black"  # bezel
        return "white" if r < 15 else "bright-black"

    user = str(ctx.get("user") or "you")[:26]
    script = [("$ ", "whoami"), ("", user), ("$ ", "cat now.txt"), ("", "building cool stuff"),
              ("$ ", "git push"), ("", "Everything up-to-date"), ("$ ", "")]
    frames, weights = [], []
    for shown in range(1, len(script) + 1):
        for cursor in ((True, False) if shown == len(script) else (True,)):
            rows = []
            for i, (prompt, text) in enumerate(script[:shown]):
                line = prompt + text + ("█" if cursor and i == shown - 1 else "")
                rows.append([None if ch == " " else (ch, "green" if prompt and j < 2 else "bright-green")
                             for j, ch in enumerate(line)])
            frames.append(rows)
            weights.append(3 if shown == len(script) else 2)
    return Logo(
        name="computer",
        art=paint(monitor, body),
        accent="bright-green",
        layers=[Layer(3, 5, frames, weights, 4.2)],
        source="candybox2",
        credit=_cb2_credit(author, "cropped to the monitor, coloured and given an animated screen"),
    )


VENDORED_EXTRAS = {"cauldron": _cauldron, "computer": _computer, "banner": _banner}


def _fastfetch(name: str) -> Logo:
    meta = _index("fastfetch")[name]
    text = (ART_DIR / "fastfetch" / meta["file"]).read_text(encoding="utf-8")
    colors = meta["colors"] or ["fg"]
    accent = next((c for c in (meta.get("keys"), meta.get("title"), colors[0]) if c and c != "fg"), "accent")
    return Logo(name=name, art=parse_dollar(text, colors), accent=accent, source="fastfetch", credit=FASTFETCH_CREDIT)


def _onefetch(name: str) -> Logo:
    meta = _index("onefetch")[name]
    text = (ART_DIR / "onefetch" / meta["file"]).read_text(encoding="utf-8")
    return Logo(name=name, art=parse_braces(text, meta["colors"]), accent=meta["colors"][0],
                source="onefetch", credit=ONEFETCH_CREDIT)


def catalog() -> list[tuple[str, str]]:
    """(name, where the art comes from) for every built-in logo."""
    out = [("drone", "readmefetch"), ("pot", "readmefetch"), ("tux", "fastfetch/neofetch + readmefetch animation"),
           ("banner", "your text in a FIGlet font")]
    out += [(n, f"Candy Box 2, by {m['author']}") for n, m in _index("candybox2").items()]
    out += [(n, "fastfetch/neofetch") for n in _index("fastfetch")]
    out += [(n, "onefetch") for n in _index("onefetch")]
    return out


CUSTOM_KEYS = {"art", "colors", "ground", "layers", "enter", "hover", "accent", "credit"}
OVERRIDE_KEYS = {"enter", "hover", "accent", "animate"}
LAYER_KEYS = {"row", "col", "frames", "weights", "period"}


def _art(text: str) -> str:
    """Art as written in TOML: the newline before the closing \'\'\' goes, leading blank rows stay."""
    return text.rstrip("\n")


def custom(name: str, spec: dict) -> Logo:
    """A logo defined in the config file under [logo.<name>]."""
    unknown = set(spec) - CUSTOM_KEYS
    if unknown:
        raise ValueError(f"[logo.{name}] unknown setting(s): {', '.join(sorted(unknown))}")
    colors = spec.get("colors", ["accent"])
    if isinstance(colors, str):
        colors = [colors]
    colors = [str(c) for c in colors] or ["accent"]
    if not isinstance(spec.get("art"), str) or not spec["art"].strip():
        raise ValueError(f"[logo.{name}] needs an `art` string")
    enter = spec.get("enter", "print")
    if enter not in ENTERS:
        raise ValueError(f"[logo.{name}] enter must be one of {', '.join(ENTERS)}")
    layers = []
    for i, ls in enumerate(spec.get("layers") or []):
        unknown = set(ls) - LAYER_KEYS
        if unknown:
            raise ValueError(f"[logo.{name}] layer {i + 1}: unknown setting(s) {', '.join(sorted(unknown))}")
        frames = [parse_dollar(_art(f), colors) for f in ls.get("frames", [])]
        if not frames:
            raise ValueError(f"[logo.{name}] layer {i + 1} has no frames")
        weights = ls.get("weights", [1] * len(frames))
        if len(weights) != len(frames):
            raise ValueError(f"[logo.{name}] layer {i + 1}: weights and frames differ in length")
        if any(float(w) <= 0 for w in weights) or float(ls.get("period", 1.0)) <= 0:
            raise ValueError(f"[logo.{name}] layer {i + 1}: weights and period must be above 0")
        layers.append(Layer(int(ls.get("row", 0)), int(ls.get("col", 0)), frames, [float(w) for w in weights],
                            float(ls.get("period", 1.0))))
    if any(layer.row < 0 or layer.col < 0 for layer in layers):
        raise ValueError(f"[logo.{name}] layer row and col can't be negative")
    return Logo(
        name=name,
        art=parse_dollar(_art(spec["art"]), colors),
        accent=str(spec.get("accent", colors[0])),
        ground=parse_dollar(_art(spec["ground"]), colors) if spec.get("ground") else [],
        layers=layers,
        enter=enter,
        hover=bool(spec.get("hover", False)),
        source="custom",
        credit=str(spec.get("credit", "")),
    )


def override(logo: Logo, spec: dict) -> Logo:
    """[logo.<built-in name>] without `art`: change how a built-in logo moves. Its credit can't change."""
    unknown = set(spec) - OVERRIDE_KEYS
    if unknown:
        hint = " (to draw your own, give it a new name)" if unknown & CUSTOM_KEYS else ""
        raise ValueError(f"[logo.{logo.name}] can only change {', '.join(sorted(OVERRIDE_KEYS))} of a built-in "
                         f"logo{hint}; unknown: {', '.join(sorted(unknown))}")
    if "enter" in spec:
        if spec["enter"] not in ENTERS:
            raise ValueError(f"[logo.{logo.name}] enter must be one of {', '.join(ENTERS)}")
        logo.enter = spec["enter"]
    if "hover" in spec:
        logo.hover = bool(spec["hover"])
    if "accent" in spec:
        logo.accent = str(spec["accent"])
    if spec.get("animate") is False:
        logo.art = logo.still()[: logo.art_rows]  # freeze every layer on its first frame
        logo.layers = []
    return logo


def builtin(name: str) -> bool:
    key = name.strip().lower()
    return key in ORIGINALS or key in VENDORED_EXTRAS or key in _index("fastfetch") or key in _index("onefetch")


def load(name: str, ctx: dict | None = None) -> Logo:
    """ctx: initials, user, banner (the [banner] table) and customs (the [logo.*] tables)."""
    ctx = ctx or {}
    customs = ctx.get("customs") or {}
    key = name.strip().lower()
    spec = customs.get(name)
    if spec is not None and ("art" in spec or not builtin(name)):
        return custom(name, spec)
    if key in ORIGINALS:
        logo = ORIGINALS[key](ctx)
    elif key in VENDORED_EXTRAS:
        logo = VENDORED_EXTRAS[key](ctx)
    elif key in _index("fastfetch"):
        logo = _fastfetch(key)
    elif key in _index("onefetch"):
        logo = _onefetch(key)
    else:
        raise ValueError(f"unknown logo {name!r}; run `readmefetch logos` to list them")
    return override(logo, spec) if spec is not None else logo


def to_dollar(grid: Grid, max_colors: int = 9) -> tuple[str, list[str]]:
    """A grid back in fastfetch syntax: (text, colours). Colours past the ninth reuse the last one."""
    colors: list[str] = []
    lines, current = [], None
    for row in grid:
        parts = []
        for cell in row:
            if cell is None:
                parts.append(" ")
                continue
            ch, color = cell
            if color not in colors and len(colors) < max_colors:
                colors.append(color)
            idx = colors.index(color) if color in colors else len(colors) - 1
            if colors[idx] != current:
                parts.append(f"${idx + 1}")
                current = colors[idx]
            parts.append("$$" if ch == "$" else ch)
        lines.append("".join(parts).rstrip())
    return "\n".join(lines), colors
