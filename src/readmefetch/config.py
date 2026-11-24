"""readmefetch.toml: loading, validation, defaults, {placeholder} expansion, and writing it back out."""

import dataclasses
import datetime as dt
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import badges as badge_mod
from . import figlet
from . import logos as logo_mod
from .themes import THEMES, palette, resolve

DEFAULT_PATH = "readmefetch.toml"
PLACEHOLDERS = {
    "user": "the `user` setting",
    "host": "the `host` setting",
    "cwd": "the `cwd` setting",
    "uptime": "time since `uptime_since`, e.g. '5 years, 6 months'",
    "repos": "public repositories of `github` (live)",
    "stars": "stars across those repositories (live)",
    "followers": "followers of `github` (live)",
    "contributions": "contributions in the last year (live, needs a token)",
    "year": "the current year",
}
GITHUB_KEYS = {"repos", "stars", "followers", "contributions"}
PROMPT_PLACEHOLDERS = ("user", "host", "cwd")

SCOPES = {
    "none": "nothing types: the output fades in line by line",
    "info": "the info on the right types itself out",
    "all": "everything under the command types itself out, the logo too",
}
DIRECTIONS = {
    "left-to-right": "each line types from its first character to its last",
    "right-to-left": "each line appears from its last character back to its first",
    "top-to-bottom": "each column fills from the top down",
    "bottom-to-top": "each column fills from the bottom up",
}
CURSORS = ("block", "bar", "underline")


@dataclass
class Prompt:
    format: str = "{user}@{host}:{cwd}$ "
    user_color: str = "green"  # {user}, {host}, and the @ between them
    cwd_color: str = "blue"


@dataclass
class Window:
    title: str = "{user}@{host}: {cwd}"
    buttons: bool = True  # the red, yellow and green dots


@dataclass
class Cursor:
    style: str = "block"
    blink: bool = True
    period: float = 1.1  # seconds per blink
    color: str = "fg"


@dataclass
class Intro:
    """How the output appears when someone opens the page (the first pass only)."""

    scope: str = "info"
    direction: str = "left-to-right"
    speed: float | None = None  # cells per second along the direction; unset: 50 across, 24 down
    variance: float = 0.5  # each line (or column) runs at speed × (1 ± variance), drawn from `seed`
    stagger: float | None = None  # seconds between one line (or column) starting and the next
    seed: int = 1
    command_speed: float = 12.5  # characters per second for the typed command

    @property
    def horizontal(self) -> bool:
        return self.direction in ("left-to-right", "right-to-left")

    @property
    def cells_per_second(self) -> float:
        return self.speed or (50.0 if self.horizontal else 24.0)

    @property
    def gap(self) -> float:
        return self.stagger if self.stagger is not None else (0.08 if self.horizontal else 0.015)


@dataclass
class Config:
    user: str = "user"
    host: str = "github"
    cwd: str = "~"
    command: str = "readmefetch"
    theme: str = "github-dark"
    colors: dict = field(default_factory=dict)
    logos: list[str] = field(default_factory=lambda: ["tux"])
    seconds_per_logo: float = 5.0
    initials: str = ""
    info: list[str] = field(default_factory=list)
    uptime_since: dt.date | None = None
    github: str = ""
    color_blocks: bool = True
    output: str = "readmefetch.svg"
    prompt: Prompt = field(default_factory=Prompt)
    window: Window = field(default_factory=Window)
    cursor: Cursor = field(default_factory=Cursor)
    intro: Intro = field(default_factory=Intro)
    banner: dict = field(default_factory=dict)
    custom_logos: dict = field(default_factory=dict)
    badges: list = field(default_factory=list)  # badges.Badge
    badge_defaults: dict = field(default_factory=lambda: badge_mod.parse([], {})[1])
    path: Path | None = None

    @property
    def title(self) -> str:
        return f"{self.user}@{self.host}"

    def window_title(self) -> str:
        return expand(self.window.title, self.prompt_values())

    def prompt_values(self) -> dict:
        return {"user": self.user, "host": self.host, "cwd": self.cwd}

    def needed_stats(self) -> set[str]:
        return {k for line in self.info for k in placeholders_in(line)} & GITHUB_KEYS

    def logo_context(self) -> dict:
        return {"initials": self.initials or (self.user[:1] + self.host[:1]).upper(), "user": self.user,
                "banner": self.banner, "customs": self.custom_logos}

    def load_logos(self) -> list:
        return [logo_mod.load(name, self.logo_context()) for name in self.logos]

    @property
    def badge_dir(self) -> Path:
        return (self.path.parent if self.path else Path(".")) / self.badge_defaults["dir"]


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; create one with `readmefetch init` or `readmefetch web`")
    with path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"{path}: {e}") from None
    return from_dict(data, path)


# --- validation ----------------------------------------------------------------------


def _text(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        raise ValueError("expected text")
    return str(v)


def _flag(v) -> bool:
    if not isinstance(v, bool):
        raise ValueError("expected true or false")
    return v


def _number(lo: float, hi: float = math.inf):
    def conv(v) -> float:
        if isinstance(v, bool):
            raise ValueError("expected a number")
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError("expected a number") from None
        if not lo <= x <= hi:
            raise ValueError(f"must be between {lo:g} and {hi:g}")
        return x
    return conv


def _whole(v) -> int:
    if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
        raise ValueError("expected a whole number")
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValueError("expected a whole number") from None


def _choice(options):
    def conv(v) -> str:
        v = _text(v).strip().lower()
        if v not in options:
            raise ValueError(f"choose one of: {', '.join(options)}")
        return v
    return conv


TABLES = {
    "prompt": (Prompt, {"format": _text, "user_color": _text, "cwd_color": _text}),
    "window": (Window, {"title": _text, "buttons": _flag}),
    "cursor": (Cursor, {"style": _choice(CURSORS), "blink": _flag, "period": _number(0.2, 10), "color": _text}),
    "intro": (Intro, {"scope": _choice(SCOPES), "direction": _choice(DIRECTIONS), "speed": _number(1, 2000),
                      "variance": _number(0, 0.95), "stagger": _number(0, 5), "seed": _whole,
                      "command_speed": _number(1, 500)}),
}
TOP_LEVEL = {
    "user", "host", "cwd", "command", "theme", "colors", "logos", "seconds_per_logo", "initials", "info",
    "uptime_since", "github", "color_blocks", "output", "logo", "banner", "badge", "badges", *TABLES,
}
BANNER_KEYS = {"text", "font", "colors", "wave"}


def _table(name: str, raw, obj, fields: dict):
    if raw is None:
        return obj
    if not isinstance(raw, dict):
        raise ValueError(f"`{name}` must be a table: [{name}]")
    unknown = set(raw) - set(fields)
    if unknown:
        raise ValueError(f"unknown setting(s) in [{name}]: {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(fields)}")
    for key, conv in fields.items():
        if raw.get(key) is None:
            continue
        try:
            setattr(obj, key, conv(raw[key]))
        except ValueError as e:
            raise ValueError(f"[{name}] {key}: {e}") from None
    return obj


def from_dict(data: dict, path: Path | None = None) -> Config:
    data = {k: v for k, v in data.items() if v is not None}
    unknown = set(data) - TOP_LEVEL
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    cfg = Config(path=path)
    for key in ("user", "host", "cwd", "command", "theme", "initials", "github", "output"):
        if key in data:
            try:
                setattr(cfg, key, _text(data[key]))
            except ValueError as e:
                raise ValueError(f"{key}: {e}") from None
    if not cfg.user.strip() or not cfg.host.strip():
        raise ValueError("`user` and `host` can't be empty")
    if cfg.theme not in THEMES:
        raise ValueError(f"unknown theme {cfg.theme!r}; choose one of: {', '.join(THEMES)}")
    if "colors" in data:
        if not isinstance(data["colors"], dict):
            raise ValueError("`colors` must be a table: [colors]")
        cfg.colors = {str(k): _text(v) for k, v in data["colors"].items()}
    if "logos" in data:
        raw = data["logos"]
        cfg.logos = [raw] if isinstance(raw, str) else [_text(x) for x in raw]
        if any(not name.strip() for name in cfg.logos):
            raise ValueError("`logos` has an empty name")
    if "seconds_per_logo" in data:
        try:
            cfg.seconds_per_logo = _number(2, 600)(data["seconds_per_logo"])
        except ValueError as e:
            raise ValueError(f"seconds_per_logo {e}") from None
    if "info" in data:
        cfg.info = [_text(x) for x in data["info"]]
    if "color_blocks" in data:
        cfg.color_blocks = _flag(data["color_blocks"])
    if data.get("uptime_since") not in (None, ""):
        v = data["uptime_since"]
        try:
            cfg.uptime_since = v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError(f"uptime_since: {v!r} is not a date like 2021-05-01") from None
        if isinstance(cfg.uptime_since, dt.datetime):
            cfg.uptime_since = cfg.uptime_since.date()
    for name, (cls, fields) in TABLES.items():
        setattr(cfg, name, _table(name, data.get(name), cls(), fields))
    cfg.custom_logos = dict(data.get("logo", {}))
    cfg.banner = dict(data.get("banner", {}))
    _check_banner(cfg.banner)
    if "badges" in data and not isinstance(data["badges"], dict):
        raise ValueError("`badges` is the table of badge defaults: [badges]; each badge is a [[badge]] table")
    cfg.badges, cfg.badge_defaults = badge_mod.parse(data.get("badge"), data.get("badges"))

    for line in cfg.info:
        for name in placeholders_in(line):
            if name not in PLACEHOLDERS:
                raise ValueError(f"unknown placeholder {{{name}}} in info line {line!r}; "
                                 f"known: {', '.join('{' + p + '}' for p in PLACEHOLDERS)}")
    for where, text in (("[prompt] format", cfg.prompt.format), ("[window] title", cfg.window.title)):
        for name in placeholders_in(text):
            if name not in PROMPT_PLACEHOLDERS:
                raise ValueError(f"unknown placeholder {{{name}}} in {where}; use {{user}}, {{host}} or {{cwd}}")
    if "uptime" in {p for line in cfg.info for p in placeholders_in(line)} and not cfg.uptime_since:
        raise ValueError("{uptime} needs `uptime_since = YYYY-MM-DD`")
    if cfg.needed_stats() and not cfg.github:
        raise ValueError(f"{', '.join('{' + s + '}' for s in sorted(cfg.needed_stats()))} need `github = \"<username>\"`")

    pal = palette(cfg.theme, cfg.colors)
    for where, color in (("[prompt] user_color", cfg.prompt.user_color), ("[prompt] cwd_color", cfg.prompt.cwd_color),
                         ("[cursor] color", cfg.cursor.color)):
        _check_color(where, color, pal)
    for i, b in enumerate(cfg.badges, 1):
        _check_color(f"[[badge]] {i} color", b.color, pal)
        if b.label_color:
            _check_color(f"[[badge]] {i} label_color", b.label_color, pal)
    for lg in cfg.load_logos():  # fail early on unknown or malformed logos, and on colours they can't show
        _check_color(f"logo {lg.name!r} accent", lg.accent, pal)
        grids = [lg.art, lg.ground] + [f for layer in lg.layers for f in layer.frames]
        for color in {cell[1] for grid in grids for row in grid for cell in row if cell}:
            _check_color(f"logo {lg.name!r}", color, pal)
    return cfg


def _check_color(where: str, color: str, pal: dict) -> None:
    try:
        resolve(color, pal)
    except ValueError as e:
        raise ValueError(f"{where}: {e}") from None


def _check_banner(spec: dict) -> None:
    unknown = set(spec) - BANNER_KEYS
    if unknown:
        raise ValueError(f"unknown setting(s) in [banner]: {', '.join(sorted(unknown))}; known: {', '.join(sorted(BANNER_KEYS))}")
    if "font" in spec and str(spec["font"]) not in figlet.fonts():
        raise ValueError(f"[banner] font: choose one of: {', '.join(figlet.fonts())}")
    if "wave" in spec:
        _flag(spec["wave"])


# --- placeholders ----------------------------------------------------------------------


def placeholders_in(text: str) -> list[str]:
    return re.findall(r"(?<!\{)\{(\w+)\}(?!\})", text)


def expand(text: str, values: dict) -> str:
    out = re.sub(r"(?<!\{)\{(\w+)\}(?!\})", lambda m: str(values.get(m.group(1), m.group(0))), text)
    return out.replace("{{", "{").replace("}}", "}")


def uptime(since: dt.date, today: dt.date) -> str:
    months = (today.year - since.year) * 12 + today.month - since.month
    if today.day < since.day:
        months -= 1
    if months < 0:
        return "not booted yet"
    y, m = divmod(months, 12)
    parts = [f"{y} year{'s' * (y != 1)}"] if y else []
    if m or not y:
        parts.append(f"{m} month{'s' * (m != 1)}")
    return ", ".join(parts)


def values(cfg: Config, stats: dict, today: dt.date) -> dict:
    v = {"user": cfg.user, "host": cfg.host, "cwd": cfg.cwd, "year": today.year}
    if cfg.uptime_since:
        v["uptime"] = uptime(cfg.uptime_since, today)
    v.update(stats)
    return v


def info_rows(cfg: Config, vals: dict) -> list[tuple[str, str] | None]:
    """Each info line -> (key, value); a line with no 'Key: ' prefix has key ''; '' -> None."""
    rows = []
    for line in cfg.info:
        text = expand(line, vals)
        if not text.strip():
            rows.append(None)
            continue
        key, sep, value = text.partition(": ")
        rows.append((key, value) if sep and key and len(key) <= 24 else ("", text))
    return rows


# --- writing a config back out (the web app's Save and Download) ----------------------


def to_dict(cfg: Config) -> dict:
    """Every setting, explicit, in the shape from_dict() reads (and the web app edits)."""
    d = {
        "user": cfg.user, "host": cfg.host, "cwd": cfg.cwd, "command": cfg.command, "theme": cfg.theme,
        "logos": list(cfg.logos), "seconds_per_logo": cfg.seconds_per_logo, "github": cfg.github,
        "uptime_since": cfg.uptime_since.isoformat() if cfg.uptime_since else "", "initials": cfg.initials,
        "color_blocks": cfg.color_blocks, "output": cfg.output, "info": list(cfg.info),
    }
    for name in TABLES:
        d[name] = {k: v for k, v in dataclasses.asdict(getattr(cfg, name)).items() if v is not None}
    d["colors"] = dict(cfg.colors)
    d["banner"] = dict(cfg.banner)
    d["logo"] = {k: dict(v) for k, v in cfg.custom_logos.items()}
    d["badges"] = {k: v for k, v in cfg.badge_defaults.items() if v != ""}
    implied = {"cursor": True, "style": cfg.badge_defaults["style"], "color": cfg.badge_defaults["color"]}
    d["badge"] = []
    for b in cfg.badges:
        implied["file"] = badge_mod.slug(b.label or b.message) + ".svg"
        d["badge"].append({k: v for k, v in dataclasses.asdict(b).items() if v != "" and implied.get(k, object()) != v})
    return d


TOP_ORDER = ["user", "host", "cwd", "command", "theme", "logos", "seconds_per_logo", "github", "uptime_since",
             "initials", "color_blocks", "output", "info"]
TABLE_NOTES = {
    "prompt": "the prompt; placeholders {user} {host} {cwd}",
    "window": "the title bar",
    "cursor": "block, bar or underline",
    "intro": ("how the output appears on a visit: scope none, info or all; direction left-to-right, "
              "right-to-left, top-to-bottom or bottom-to-top"),
    "colors": "override theme colours",
    "banner": "the `banner` logo: your text in a FIGlet font",
    "badges": "defaults for the [[badge]] tables below; styles: flat, flat-square, plastic, for-the-badge, pill, terminal",
}
OPTIONAL = {"github", "initials", "uptime_since"}  # left out when empty


def dump(data: dict) -> str:
    """A readmefetch.toml for `data` (the shape to_dict() returns). TOML has no comments to keep, so this
    writes short notes of its own."""
    out = ["# readmefetch: https://github.com/aurelioochoa/readmefetch",
           "# Preview: readmefetch print · render: readmefetch render · edit in a browser: readmefetch web", ""]
    for key in TOP_ORDER + sorted(set(data) - set(TOP_ORDER) - set(TABLES) - {"colors", "banner", "logo", "badges", "badge"}):
        if key not in data or (key in OPTIONAL and data[key] in ("", None)):
            continue
        out.append(f"{key} = {_toml(data[key], key)}")
    for name in [*TABLES, "colors", "banner", "badges"]:
        table = {k: v for k, v in (data.get(name) or {}).items() if v is not None}
        if not table:
            continue
        out += ["", f"# {TABLE_NOTES[name]}", f"[{name}]"]
        out += [f"{_key(k)} = {_toml(v, k)}" for k, v in table.items()]
    for name, spec in (data.get("logo") or {}).items():
        out += ["", f"[logo.{_key(name)}]"]
        out += [f"{_key(k)} = {_toml(v, k)}" for k, v in spec.items() if k != "layers" and v is not None]
        for layer in spec.get("layers") or []:
            out += ["", f"[[logo.{_key(name)}.layers]]"]
            out += [f"{_key(k)} = {_toml(v, k)}" for k, v in layer.items() if v is not None]
    for badge in data.get("badge") or []:
        out += ["", "[[badge]]"]
        out += [f"{_key(k)} = {_toml(v, k)}" for k, v in badge.items() if v is not None and v != ""]
    return "\n".join(out) + "\n"


def _key(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else _basic(k)


def _basic(s: str) -> str:
    esc = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
    return '"' + "".join(esc.get(ch, f"\\u{ord(ch):04x}" if ord(ch) < 32 or ord(ch) == 127 else ch) for ch in s) + '"'


def _string(s: str) -> str:
    if "\n" not in s:
        return _basic(s)
    if "'''" not in s and not re.search(r"[\x00-\x08\x0b-\x1f\x7f]", s):
        return "'''\n" + s + ("" if s.endswith("\n") else "\n") + "'''"  # literal: backslashes stay as typed
    body = _basic(s)[1:-1].replace("\\n", "\n")
    return '"""\n' + body + ("" if s.endswith("\n") else "\n") + '"""'


def _toml(v, key: str = "") -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"{key}: {v} can't be written to TOML")
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        if key == "uptime_since" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return v
        return _string(v)
    if isinstance(v, (list, tuple)):
        items = [_toml(x, key) for x in v]
        if key in ("info", "frames") or any("\n" in i for i in items) or sum(len(i) + 2 for i in items) > 90:
            return "[\n" + "".join(f"  {i},\n" for i in items) + "]"
        return "[" + ", ".join(items) + "]"
    raise ValueError(f"{key}: can't write {type(v).__name__} to TOML")


TEMPLATE = '''# readmefetch: your GitHub profile as an animated terminal.
# Preview with `readmefetch print`, render with `readmefetch render`, or edit it in a browser
# with `readmefetch web`. Every setting: https://github.com/aurelioochoa/readmefetch#configuration

user = "{user}"
host = "{host}"
cwd = "~"                       # the directory in the prompt and title bar
command = "readmefetch"         # what gets typed at the prompt
theme = "github-dark"           # see `readmefetch themes`
logos = ["tux", "{lang}", "drone"]  # cycled in order; see `readmefetch logos`
seconds_per_logo = 5
output = "readmefetch.svg"
{github_line}
uptime_since = {since}          # {{uptime}} counts from here

info = [
  "OS: {bio}",
  "Host: {location}",
  "Uptime: {{uptime}}",
  "Shell: bash",
  "",
  "Languages: Python · TypeScript · Go",
  "Editor: neovim",
  "",
{github_info}  "Contact: {blog}",
]

# How the output appears when someone opens your profile (only the first time through).
[intro]
scope = "info"                  # none, info (the text on the right) or all (the logo too)
direction = "left-to-right"     # right-to-left, top-to-bottom, bottom-to-top
variance = 0.5                  # 0: every line at the same speed; 0.9: very uneven
seed = 1                        # change it for a different mix of speeds
# speed = 50                    # characters per second (default 50 across, 24 down)
# stagger = 0.08                # seconds between one line starting and the next

[cursor]
style = "block"                 # block, bar or underline
blink = true

# [prompt]
# format = "{{user}}@{{host}}:{{cwd}}$ "   # try "{{cwd}} > " or "[{{user}}@{{host}} {{cwd}}]$ "
# user_color = "green"
# cwd_color = "blue"

# [window]
# title = "{{user}}@{{host}}: {{cwd}}"
# buttons = true

# [colors]                      # override any theme colour
# accent = "#00d4ff"

# Change how a built-in logo moves:
# [logo.tux]
# enter = "fade"                # print (line by line), fly (in from the top) or fade
# hover = true                  # gentle bobbing
# animate = false               # no blinking, spinning or flickering

# A logo of your own, in fastfetch's syntax ($1..$9 pick from `colors`).
# Use \'\'\' literal strings so backslashes stay backslashes.
# [logo.mine]
# colors = ["bright-cyan", "white"]
# art = \'\'\'
# $1  /\\
# $1 /  \\  $2hello
# $1/____\\
# \'\'\'
# credit = "art by ..."         # shown by `readmefetch logos` and kept in the SVG

# Badges for your links: `readmefetch badges` writes them and prints the README lines.
# Styles: flat, flat-square, plastic, for-the-badge, pill, terminal.
# Icons: globe, mail, link, code, terminal, game, cards, tree, briefcase, heart, star,
# home, rocket, book, or the d attribute of a 24x24 SVG path.
# [badges]
# style = "for-the-badge"
# dir = "badges"                # relative to this file
#
# [[badge]]
# label = "Website"
# message = "example.com"
# link = "https://example.com"
# color = "accent"              # a theme colour name or #hex
# icon = "globe"
'''
