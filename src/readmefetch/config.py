"""readmefetch.toml: loading, defaults and {placeholder} expansion."""

import datetime as dt
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import logos as logo_mod
from .themes import THEMES

DEFAULT_PATH = "readmefetch.toml"
PLACEHOLDERS = {
    "user": "the `user` setting",
    "host": "the `host` setting",
    "uptime": "time since `uptime_since`, e.g. '5 years, 6 months'",
    "repos": "public repositories of `github` (live)",
    "stars": "stars across those repositories (live)",
    "followers": "followers of `github` (live)",
    "contributions": "contributions in the last year (live, needs a token)",
    "year": "the current year",
}
GITHUB_KEYS = {"repos", "stars", "followers", "contributions"}


@dataclass
class Config:
    user: str = "user"
    host: str = "github"
    command: str = "neofetch"
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
    banner: dict = field(default_factory=dict)
    custom_logos: dict = field(default_factory=dict)
    path: Path | None = None

    @property
    def title(self) -> str:
        return f"{self.user}@{self.host}"

    def needed_stats(self) -> set[str]:
        return {k for line in self.info for k in placeholders_in(line)} & GITHUB_KEYS

    def logo_context(self) -> dict:
        return {"initials": self.initials or (self.user[:1] + self.host[:1]).upper(), "user": self.user,
                "banner": self.banner, "customs": self.custom_logos}

    def load_logos(self) -> list:
        return [logo_mod.load(name, self.logo_context()) for name in self.logos]


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; create one with `readmefetch init`")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return from_dict(data, path)


def from_dict(data: dict, path: Path | None = None) -> Config:
    known = {
        "user", "host", "command", "theme", "colors", "logos", "seconds_per_logo", "initials",
        "info", "uptime_since", "github", "color_blocks", "output", "logo", "banner",
    }
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    cfg = Config(path=path)
    for key in ("user", "host", "command", "theme", "initials", "github", "output"):
        if key in data:
            setattr(cfg, key, str(data[key]))
    if cfg.theme not in THEMES:
        raise ValueError(f"unknown theme {cfg.theme!r}; choose one of: {', '.join(THEMES)}")
    if "colors" in data:
        cfg.colors = {str(k): str(v) for k, v in data["colors"].items()}
    if "logos" in data:
        cfg.logos = [data["logos"]] if isinstance(data["logos"], str) else [str(x) for x in data["logos"]]
    if "seconds_per_logo" in data:
        cfg.seconds_per_logo = float(data["seconds_per_logo"])
        if cfg.seconds_per_logo < 2:
            raise ValueError("seconds_per_logo must be at least 2")
    if "info" in data:
        cfg.info = [str(x) for x in data["info"]]
    if "color_blocks" in data:
        cfg.color_blocks = bool(data["color_blocks"])
    if "uptime_since" in data:
        v = data["uptime_since"]
        cfg.uptime_since = v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))
        if isinstance(cfg.uptime_since, dt.datetime):
            cfg.uptime_since = cfg.uptime_since.date()
    cfg.custom_logos = dict(data.get("logo", {}))
    cfg.banner = dict(data.get("banner", {}))
    for line in cfg.info:
        for name in placeholders_in(line):
            if name not in PLACEHOLDERS:
                raise ValueError(f"unknown placeholder {{{name}}} in info line {line!r}; "
                                 f"known: {', '.join('{' + p + '}' for p in PLACEHOLDERS)}")
    if "uptime" in {p for line in cfg.info for p in placeholders_in(line)} and not cfg.uptime_since:
        raise ValueError("{uptime} needs `uptime_since = YYYY-MM-DD`")
    if cfg.needed_stats() and not cfg.github:
        raise ValueError(f"{', '.join('{' + s + '}' for s in sorted(cfg.needed_stats()))} need `github = \"<username>\"`")
    cfg.load_logos()  # fail early on unknown or malformed logos
    return cfg


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
    v = {"user": cfg.user, "host": cfg.host, "year": today.year}
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


TEMPLATE = '''# readmefetch: your GitHub profile as an animated terminal running neofetch.
# Render with `readmefetch render`, preview in your terminal with `readmefetch print`.
# Every setting: https://github.com/aurelioochoa/readmefetch#configuration

user = "{user}"
host = "{host}"
command = "neofetch"            # what gets typed at the prompt
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

# [colors]                      # override any theme colour
# accent = "#00d4ff"

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
'''
