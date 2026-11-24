#!/usr/bin/env python3
"""Refresh the third-party art in src/readmefetch/art/ from pinned upstream commits.

    python3 tools/vendor_art.py

The art files are copied byte-for-byte (fastfetch `.txt`, onefetch `ascii` blocks)
so their provenance stays checkable; only metadata (colours, authors) is extracted to JSON.
Each source keeps its own licence file next to its art (MIT, BSD-3-Clause, CC0,
CC BY-SA 3.0).
See CREDITS.md.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "src" / "readmefetch" / "art"

FASTFETCH = "fastfetch-cli/fastfetch"
FASTFETCH_SHA = "e09925d303dfc1d3cb35b977017d65c9c1704366"
ONEFETCH = "o2sh/onefetch"
ONEFETCH_SHA = "8b63584a505a3225ff85dc7144c910eb48f5c12a"
NEOFETCH = "dylanaraps/neofetch"
NEOFETCH_SHA = "ccd5d9f52609bbdcd5d8fa78c4fdb0f12954125f"  # last commit; the repository is archived

# readmefetch name -> fastfetch file stem
FASTFETCH_LOGOS = {
    "linux": "linux", "arch": "arch", "debian": "debian", "ubuntu": "ubuntu",
    "fedora": "fedora", "macos": "macos", "windows": "windows_11", "nixos": "nixos",
    "raspbian": "raspbian", "android": "android", "mint": "linuxmint", "pop": "pop",
    "kali": "kali", "gentoo": "gentoo", "manjaro": "manjaro", "freebsd": "freebsd",
    "alpine": "alpine", "opensuse": "opensuse",
}
# readmefetch name -> onefetch languages.yaml key
ONEFETCH_LOGOS = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "php": "Php", "java": "Java", "lua": "Lua", "rust": "Rust", "go": "Go",
    "html": "Html", "css": "Css", "sass": "Sass", "vue": "Vue", "c": "C",
    "cpp": "Cpp", "csharp": "CSharp", "ruby": "Ruby", "kotlin": "Kotlin",
    "swift": "Swift", "dart": "Dart", "bash": "Bash", "docker": "Dockerfile",
}

CANDYBOX2 = "candybox2/candybox2.github.io"
CANDYBOX2_SHA = "35301d438aa2c1e58e8cb3ea215b0af323bddf9b"
CANDYBOX2_ART = {  # readmefetch name -> file
    "cauldron": "ascii/places/cauldron/cauldron.txt",  # @author dixsept
    "computer": "ascii/general/theComputer/computer.txt",  # @author aniwey (readmefetch shows the monitor only)
}
CANDYBOX2_LICENSE = """\
# Candy Box 2 ASCII art

The files in this folder are ASCII art from Candy Box 2
(https://github.com/candybox2/candybox2.github.io), copied unmodified.

They are licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported
licence (CC BY-SA 3.0): https://creativecommons.org/licenses/by-sa/3.0/
They are NOT covered by readmefetch's MIT licence.

Each file's first line ("@author ...") names the artist, as the Candy Box 2 ascii art
page asks (https://candybox2.github.io/ascii_art.html). readmefetch writes the artist,
the licence and any changes it makes (recolouring, animation, cropping) into every
SVG that uses one of these pieces; keep that notice if you share the SVG.
"""

FIGLET = "cmatsuoka/figlet"
FIGLET_SHA = "202a0a8110650a943f1125f536b3bb455cf72ee1"
FIGLET_FONTS = ["standard", "slant", "small", "smslant", "big"]
PHANTOMWISE = "Phantomwise/ascii"
PHANTOMWISE_SHA = "c0a4c06e6477f1fbedfa186a1c66f575b08dac74"

ANSI = {
    "BLACK": "black", "RED": "red", "GREEN": "green", "YELLOW": "yellow",
    "BLUE": "blue", "MAGENTA": "magenta", "CYAN": "cyan", "WHITE": "white",
}


def fetch(repo: str, sha: str, path: str) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def xterm256(n: int) -> str:
    if n < 16:
        names = list(ANSI.values())
        return names[n] if n < 8 else "bright-" + names[n - 8]
    if n < 232:
        n -= 16
        lv = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (lv[n // 36], lv[n // 6 % 6], lv[n % 6])
    g = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (g, g, g)


def ff_color(token: str) -> str:
    """One fastfetch colour expression -> a readmefetch colour (theme name or hex)."""
    token = token.strip()
    m = re.fullmatch(r'FF_COLOR_FG_256\s*"(\d+)"', token)
    if m:
        return xterm256(int(m.group(1)))
    m = re.fullmatch(r'FF_COLOR_FG_RGB\s*"(\d+);(\d+);(\d+)"', token)
    if m:
        return "#%02x%02x%02x" % tuple(int(x) for x in m.groups())
    m = re.fullmatch(r"FF_COLOR_FG_(LIGHT_)?([A-Z]+)", token)
    if m:
        if m.group(2) == "DEFAULT":
            return "fg"
        return ("bright-" if m.group(1) else "") + ANSI[m.group(2)]
    raise ValueError(f"unknown fastfetch colour {token!r}")


def ff_entry(inc: str, stem: str) -> dict:
    macro = "FASTFETCH_DATATEXT_LOGO_" + stem.upper()
    m = re.search(r"\.lines\s*=\s*" + macro + r"\s*,(.*?)#endif", inc, re.S)
    if not m:
        raise LookupError(f"{macro} not found")
    body = m.group(1)
    colors = re.search(r"\.colors\s*=\s*{(.*?)}", body, re.S)
    items = [c for c in (x.strip() for x in colors.group(1).split(",")) if c] if colors else []
    entry = {"colors": [ff_color(c) for c in items]}
    for key, field in (("keys", "colorKeys"), ("title", "colorTitle")):
        km = re.search(r"\." + field + r"\s*=\s*([^,\n]+)", body)
        if km:
            entry[key] = ff_color(km.group(1))
    return entry


def onefetch_languages(yaml_text: str, wanted: set[str]) -> dict:
    """Tiny parser for the parts of onefetch's languages.yaml we need."""
    out, name, lines = {}, None, yaml_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        top = re.fullmatch(r"([A-Za-z0-9+#_-]+):\s*", line)
        if top:
            name = top.group(1)
            i += 1
            continue
        if name in wanted and line.startswith("  ascii: |"):
            art = []
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                art.append(lines[i][4:])
                i += 1
            while art and not art[-1].strip():
                art.pop()
            out.setdefault(name, {})["ascii"] = "\n".join(art) + "\n"
            continue
        if name in wanted and line.strip() in ("hex:", "ansi:"):
            kind, values = line.strip()[:-1], []
            i += 1
            while i < len(lines) and lines[i].strip().startswith("- "):
                values.append(lines[i].strip()[2:].strip().strip("\"'"))
                i += 1
            out.setdefault(name, {})[kind] = values
            continue
        i += 1
    return out


def main() -> int:
    ff_dir = ART / "fastfetch"
    of_dir = ART / "onefetch"
    ff_dir.mkdir(parents=True, exist_ok=True)
    of_dir.mkdir(parents=True, exist_ok=True)

    (ff_dir / "LICENSE").write_text(fetch(FASTFETCH, FASTFETCH_SHA, "LICENSE"))
    (ff_dir / "LICENSE.neofetch").write_text(fetch(NEOFETCH, NEOFETCH_SHA, "LICENSE.md"))
    incs: dict[str, str] = {}
    index = {"source": f"https://github.com/{FASTFETCH}/tree/{FASTFETCH_SHA}/src/logo/ascii", "logos": {}}
    for name, stem in FASTFETCH_LOGOS.items():
        letter = stem[0]
        if letter not in incs:
            incs[letter] = fetch(FASTFETCH, FASTFETCH_SHA, f"src/logo/ascii/{letter}.inc")
        (ff_dir / f"{stem}.txt").write_text(fetch(FASTFETCH, FASTFETCH_SHA, f"src/logo/ascii/{letter}/{stem}.txt"))
        index["logos"][name] = {"file": f"{stem}.txt", **ff_entry(incs[letter], stem)}
    (ff_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")

    (of_dir / "LICENSE").write_text(fetch(ONEFETCH, ONEFETCH_SHA, "LICENSE.md"))
    langs = onefetch_languages(fetch(ONEFETCH, ONEFETCH_SHA, "languages.yaml"), set(ONEFETCH_LOGOS.values()))
    index = {"source": f"https://github.com/{ONEFETCH}/blob/{ONEFETCH_SHA}/languages.yaml", "logos": {}}
    for name, key in ONEFETCH_LOGOS.items():
        lang = langs[key]
        (of_dir / f"{name}.txt").write_text(lang["ascii"])
        # exact hex colours when onefetch has them, otherwise its ANSI names (themed)
        colors = lang.get("hex") or [c.replace("bright_", "bright-") for c in lang["ansi"]]
        index["logos"][name] = {"file": f"{name}.txt", "language": key, "colors": colors}
    (of_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")

    # Candy Box 2 art: CC BY-SA 3.0, each file names its artist on an "@author" line.
    cb_dir = ART / "candybox2"
    cb_dir.mkdir(parents=True, exist_ok=True)
    index = {"source": f"https://github.com/{CANDYBOX2}/tree/{CANDYBOX2_SHA}/ascii",
             "license": "CC BY-SA 3.0", "license_url": "https://creativecommons.org/licenses/by-sa/3.0/", "logos": {}}
    for name, path in CANDYBOX2_ART.items():
        text = fetch(CANDYBOX2, CANDYBOX2_SHA, path)
        first, _, _ = text.partition("\n")
        if not first.startswith("@author "):
            raise ValueError(f"{path} has no @author line; it cannot be credited, so it is not vendored")
        (cb_dir / f"{name}.txt").write_text(text)
        index["logos"][name] = {"file": f"{name}.txt", "path": path, "author": first[len("@author "):].strip()}
    (cb_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    (cb_dir / "LICENSE.md").write_text(CANDYBOX2_LICENSE)

    # FIGlet fonts for banner logos.
    fig_dir = ART / "figlet"
    fig_dir.mkdir(parents=True, exist_ok=True)
    (fig_dir / "LICENSE").write_text(fetch(FIGLET, FIGLET_SHA, "LICENSE"))
    for font in FIGLET_FONTS:
        (fig_dir / f"{font}.flf").write_text(fetch(FIGLET, FIGLET_SHA, f"fonts/{font}.flf"))
    (fig_dir / "tubes.flf").write_text(fetch(PHANTOMWISE, PHANTOMWISE_SHA, "figfonts/Tubes-Regular.flf"))
    (fig_dir / "LICENSE.tubes").write_text(fetch(PHANTOMWISE, PHANTOMWISE_SHA, "LICENSE"))

    print(f"vendored {len(FASTFETCH_LOGOS)} fastfetch, {len(ONEFETCH_LOGOS)} onefetch and "
          f"{len(CANDYBOX2_ART)} Candy Box 2 logos, and {len(FIGLET_FONTS) + 1} FIGlet fonts into {ART}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
