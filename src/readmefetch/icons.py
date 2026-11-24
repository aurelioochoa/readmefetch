"""Vector icons for info lines and badges: `:repo:`, `:python:`, `:nf-dev-python:`.

GitHub shows README images through <img>, which can't load fonts, so a Nerd Font
glyph would be an empty box for most visitors. These are the same icons drawn as
SVG shapes instead, copied from Octicons (MIT), Simple Icons (CC0), font-logos
(Unlicense) and Devicon (MIT) by tools/vendor_icons.py. Each icon is defined once
per SVG as a <symbol> and placed with <use>, and takes the colour of its text.

In a terminal (`readmefetch print --nerd-font`) the real Nerd Font glyph is printed.
"""

import functools
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

DATA = Path(__file__).parent / "art" / "icons" / "icons.json"
# :name: with an optional Nerd Font prefix; names are lowercase letters, digits, - and _
SHORTCODE = re.compile(r":((?:nf-)?[a-z0-9][a-z0-9_#+-]*):")


@functools.cache
def data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def lookup(name: str) -> str | None:
    """A short name, a Nerd Font name or a source key -> the icon's key, or None."""
    d = data()
    name = name.strip().lower()
    if name in d["icons"]:
        return name
    if name.startswith("nf-"):
        return d["nerd"].get(name)
    return d["short"].get(name)


def get(key: str) -> dict:
    return data()["icons"][key]


def names() -> dict[str, str]:
    """Every short name -> its key."""
    return data()["short"]


def symbol_id(key: str) -> str:
    return "i-" + re.sub(r"[^a-z0-9-]", "-", key)


def symbol(key: str) -> str:
    icon = get(key)
    x, y, w, h = icon["box"]
    return f'<symbol id="{symbol_id(key)}" viewBox="{x:g} {y:g} {w:g} {h:g}">{icon["svg"]}</symbol>'


def standalone(key: str, size: float, color: str) -> str:
    """The icon as a complete <svg> (thumbnails in the web editor)."""
    icon = get(key)
    x, y, w, h = icon["box"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size:g}" height="{size:g}" viewBox="{x:g} {y:g} {w:g} {h:g}" '
            f'fill="{escape(color)}">{icon["svg"]}</svg>')


def nested(key: str, x: float, y: float, size: float, color: str) -> str:
    """The icon placed at (x, y) inside another SVG, without <defs> (badges)."""
    icon = get(key)
    bx, by, w, h = icon["box"]
    return (f'<svg x="{x:.2f}" y="{y:.2f}" width="{size:g}" height="{size:g}" viewBox="{bx:g} {by:g} {w:g} {h:g}" '
            f'fill="{escape(color)}">{icon["svg"]}</svg>')


def glyph(key: str) -> str:
    """The Nerd Font character for an icon, or '' when Nerd Fonts has none."""
    code = get(key).get("nf")
    return chr(int(code, 16)) if code else ""


def credit(keys) -> str:
    """One line naming the icon sets a drawing uses, for the SVG's comments."""
    d = data()
    used = sorted({get(k)["src"] for k in keys})
    return "; ".join(f"{d['sources'][s]['name']} ({d['sources'][s]['licence']})" for s in used)


def catalog() -> list[dict]:
    """Every icon once, under its own name (aliases like py or pr kept for search), for the editor's picker."""
    d = data()
    names: dict[str, list[str]] = {}
    for name, key in d["short"].items():
        names.setdefault(key, []).append(name)
    best = {}
    for key, ns in names.items():
        own = key.split("-", 1)[1]
        best[key] = own if own in ns else min(ns, key=len)
    groups = {"octicons": "GitHub", "simple-icons": "Brands", "devicon": "Brands", "font-logos": "Linux and desktops"}
    out = []
    for key, name in best.items():
        icon = d["icons"][key]
        nerd = [n for n, k in d["nerd"].items() if k == key and n.split("-")[1] in ("oct", "dev", "linux")]
        out.append({"name": name, "key": key, "group": groups[icon["src"]], "title": icon.get("title", name),
                    "aliases": sorted(n for n in names[key] if n != name),
                    "nerd": nerd[0] if nerd else "", "hex": icon.get("hex", ""), "box": icon["box"], "svg": icon["svg"]})
    order = {"GitHub": 0, "Brands": 1, "Linux and desktops": 2}
    return sorted(out, key=lambda i: (order[i["group"]], i["name"]))
