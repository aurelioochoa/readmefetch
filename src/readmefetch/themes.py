"""Colour themes. Each theme names the window colours and a 16-colour terminal palette.

Logos and config refer to colours by name ("red", "bright-blue", "accent", "fg",
"dim", ...) so they follow whatever theme is chosen; "#rrggbb" always works too.
"""

import re

NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]


def _theme(bg, bar, border, fg, dim, accent, normal, bright):
    t = {"bg": bg, "bar": bar, "border": border, "fg": fg, "dim": dim, "accent": accent}
    t.update(zip(NAMES, normal))
    t.update(("bright-" + n, c) for n, c in zip(NAMES, bright))
    return t


THEMES = {
    "github-dark": _theme(
        "#0d1117", "#161b22", "#30363d", "#c9d1d9", "#8b949e", "#58a6ff",
        ["#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"],
        ["#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#f0f6fc"],
    ),
    "github-light": _theme(
        "#ffffff", "#f6f8fa", "#d0d7de", "#1f2328", "#656d76", "#0969da",
        ["#24292f", "#cf222e", "#116329", "#4d2d00", "#0969da", "#8250df", "#1b7c83", "#6e7781"],
        ["#57606a", "#a40e26", "#1a7f37", "#633c01", "#218bff", "#a475f9", "#3192aa", "#8c959f"],
    ),
    "dracula": _theme(
        "#282a36", "#21222c", "#44475a", "#f8f8f2", "#6272a4", "#bd93f9",
        ["#21222c", "#ff5555", "#50fa7b", "#f1fa8c", "#bd93f9", "#ff79c6", "#8be9fd", "#f8f8f2"],
        ["#6272a4", "#ff6e6e", "#69ff94", "#ffffa5", "#d6acff", "#ff92df", "#a4ffff", "#ffffff"],
    ),
    "tokyo-night": _theme(
        "#1a1b26", "#16161e", "#292e42", "#c0caf5", "#565f89", "#7aa2f7",
        ["#15161e", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#a9b1d6"],
        ["#414868", "#ff899d", "#9fe044", "#faba4a", "#8db0ff", "#c7a9ff", "#a4daff", "#c0caf5"],
    ),
    "catppuccin-mocha": _theme(
        "#1e1e2e", "#181825", "#313244", "#cdd6f4", "#6c7086", "#89b4fa",
        ["#45475a", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7", "#94e2d5", "#bac2de"],
        ["#585b70", "#f37799", "#89d88b", "#ebd391", "#74a8fc", "#f2aede", "#6bd7ca", "#a6adc8"],
    ),
    "gruvbox-dark": _theme(
        "#282828", "#1d2021", "#3c3836", "#ebdbb2", "#928374", "#fabd2f",
        ["#282828", "#cc241d", "#98971a", "#d79921", "#458588", "#b16286", "#689d6a", "#a89984"],
        ["#928374", "#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c", "#ebdbb2"],
    ),
    "nord": _theme(
        "#2e3440", "#3b4252", "#4c566a", "#d8dee9", "#7b88a1", "#88c0d0",
        ["#3b4252", "#bf616a", "#a3be8c", "#ebcb8b", "#81a1c1", "#b48ead", "#88c0d0", "#e5e9f0"],
        ["#4c566a", "#bf616a", "#a3be8c", "#ebcb8b", "#81a1c1", "#b48ead", "#8fbcbb", "#eceff4"],
    ),
}

ALIASES = {"default": "fg", "gray": "bright-black", "grey": "bright-black", "foreground": "fg"}
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")


def palette(theme: str, overrides: dict | None = None) -> dict:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose one of: {', '.join(THEMES)}")
    pal = dict(THEMES[theme])
    for key, value in (overrides or {}).items():
        key = normalize(key)
        if key not in pal:
            raise ValueError(f"unknown colour name {key!r} in [colors]")
        pal[key] = resolve(value, pal)
    return pal


def normalize(name: str) -> str:
    name = name.strip().lower().replace("_", "-")
    name = re.sub(r"^(light|bright)-?", "bright-", name)
    return ALIASES.get(name, name)


def resolve(color: str, pal: dict) -> str:
    """Theme colour name or #hex -> #hex."""
    if HEX.fullmatch(color.strip()):
        return color.strip().lower()
    name = normalize(color)
    if name not in pal:
        raise ValueError(f"unknown colour {color!r}: use a theme colour name ({', '.join(sorted(pal))}) or #rrggbb")
    return pal[name]


def hex_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
