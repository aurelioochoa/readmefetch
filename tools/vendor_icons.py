#!/usr/bin/env python3
"""Refresh the vector icons in src/readmefetch/art/icons/ from pinned upstream releases.

    python3 tools/vendor_icons.py [--cache DIR]

GitHub shows README images through <img>, which can't load fonts, so Nerd Font
glyphs would show as empty boxes for most visitors. readmefetch draws its icons as
SVG shapes instead, copied from free icon sets (the same sets Nerd Fonts patches in):

    Octicons      MIT       GitHub's own icons: repo, star, commit, pull request ...
    Simple Icons  CC0-1.0   brand logos: languages, tools, sites
    font-logos    Unlicense Linux distributions and desktops (Nerd Fonts' nf-linux-*)
    Devicon       MIT       dev logos Simple Icons doesn't have (Nerd Fonts' nf-dev-*)

Simple Icons is CC0 as a whole, but some of its logos carry their owners' own licence
(MIT, CC BY-SA, GPL, non-commercial ...), listed in its data file. Those are never
bundled: Devicon's MIT drawing of the same logo is used instead, or the logo is left out.

Only a curated set is kept (the lists below). Shapes are copied as they are; only
colours are dropped so an icon takes the colour of the text around it. Nerd Fonts'
glyphnames.json (MIT) maps nf-* names and codepoints, so `:nf-dev-python:` works and
`readmefetch print --nerd-font` can print the real glyph. See CREDITS.md.
"""

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "readmefetch" / "art" / "icons"

OCTICONS = "19.42.0"
SIMPLE_ICONS = "16.38.1"
DEVICON = "2.18.0"
FONT_LOGOS = "v1.4.0"
NERD_FONTS = "v3.5.1"

JSDELIVR = "https://cdn.jsdelivr.net/npm"
RAW = "https://raw.githubusercontent.com"

# GitHub and general-purpose glyphs (Octicons, 16px versions).
OCT = """repo star star-fill people person person-add git-commit git-pull-request git-merge git-branch issue-opened
issue-closed repo-forked code-review comment-discussion flame calendar clock history location mail link globe
organization briefcase heart heart-fill code terminal book rocket mark-github eye graph pulse zap gift trophy package
tag tools gear cpu server database device-desktop device-mobile home light-bulb megaphone mortar-board pencil
sparkle-fill sun moon beaker bug codespaces copilot file-code apps workflow broadcast telescope verified shield-check
rss north-star hubot paintbrush image video stack smiley thumbsup project milestone checklist inbox log container
cloud key lock unlock sponsor-tiers dependabot paper-airplane command-palette goal infinity hourglass stopwatch play
mention hash bookmark sync download upload file file-directory repo-template repo-push code-of-conduct law note pin
plug report question info alert check x plus dash arrow-right chevron-right dot-fill circle square-fill copy filter
search share-android unfold versions webhook feed-star feed-heart list-unordered browser screen-full screen-normal
undo trash grabber rows multi-select sliders typography tab-external no-entry desktop-download""".split()

# Brands (Simple Icons slugs).
SI = """python javascript typescript go rust c cplusplus openjdk kotlin swift dart flutter ruby php lua gnubash
html5 css sass react vuedotjs angular svelte nextdotjs nodedotjs deno bun express laravel django flask fastapi spring
dotnet docker kubernetes git github gitlab linux ubuntu debian archlinux fedora apple android vim neovim jetbrains
nginx apache mysql postgresql mongodb redis sqlite firebase googlecloud googleappsscript jenkins
githubactions terraform ansible vault
wordpress figma blender unity godotengine tailwindcss bootstrap jquery threedotjs webpack vite npm yarn pnpm tensorflow
pytorch numpy pandas jupyter r julia haskell elixir erlang scala clojure zig nim ocaml fsharp perl markdown json yaml
latex raspberrypi arduino electron graphql prometheus grafana vercel netlify cloudflare digitalocean trello jira notion
discord stackoverflow x youtube twitch medium devdotto bluesky mastodon instagram reddit hashnode kofi buymeacoffee
patreon spotify steam itchdotio leetcode hackerrank kaggle telegram whatsapp signal matrix threads tiktok gmail
protonmail obsidian homebrew forgejo gitea codeberg nextcloud tailscale proxmox jellyfin plex homeassistant
letsencrypt anthropic claude dji gnome kde xfce i3 sway hyprland wayland zsh fishshell alacritty kitty wezterm iterm2
tmux gnu sublimetext arc firefox googlechrome brave vivaldi opera thunderbird githubcopilot ollama huggingface stripe
paypal hackthebox tryhackme duolingo goodreads letterboxd lichess chessdotcom playstation retroarch steamdeck
epicgames roblox gamemaker aseprite inkscape gimp krita audacity davinciresolve dribbble behance artstation pinterest
substack ghost hugo jekyll eleventy gatsby astro""".split()

# Dev logos Simple Icons no longer carries (Devicon; plain version, else the single-colour original).
DEV = """csharp java powershell windows11 vscode amazonwebservices azure heroku slack linkedin codepen emacs""".split()

# Simple Icons logos under a licence of their own are taken from Devicon (MIT) instead.
SI_FREE = {"CC0-1.0", "Unlicense"}  # licences that ask nothing of us
SI_TO_DEV = {"openjdk": "java", "gnubash": "bash", "vuedotjs": "vuejs", "deno": "denojs", "godotengine": "godot",
             "fishshell": "fish"}  # where Devicon's name differs

# Short names for icons whose slug is awkward to type.
ALIASES = {
    "bash": "gnubash", "css3": "css", "vue": "vuedotjs", "vuejs": "vuedotjs", "nextjs": "nextdotjs",
    "node": "nodedotjs", "nodejs": "nodedotjs", "threejs": "threedotjs", "godot": "godotengine", "cpp": "cplusplus",
    "devto": "devdotto", "itchio": "itchdotio", "chess": "chessdotcom", "fish": "fishshell", "chrome": "googlechrome",
    "gcp": "googlecloud", "appsscript": "googleappsscript",
    "aws": "amazonwebservices", "k8s": "kubernetes", "ts": "typescript", "js": "javascript",
    "py": "python", "golang": "go", "twitter": "x", "windows": "windows11",
    "rpi": "raspberrypi", "github-actions": "githubactions", "postgres": "postgresql",
    "jdk": "openjdk", "c#": "csharp", "f#": "fsharp", "commit": "git-commit",
    "pr": "git-pull-request", "pull-request": "git-pull-request", "issue": "issue-opened", "fork": "repo-forked",
    "review": "code-review", "followers": "people", "streak": "flame", "contributions": "graph", "stars": "star",
    "repos": "repo", "location-pin": "location", "email": "mail", "web": "globe", "website": "globe",
    "drone": "dji", "pilot": "dji", "work": "briefcase", "job": "briefcase", "school": "mortar-board",
    "education": "mortar-board", "languages": "code", "editor": "pencil", "shell": "terminal", "os": "tux",
    "uptime": "clock", "host": "device-desktop",
}

FL_SKIP = {"openbsd"}  # 40 KB of shapes
MAX_BYTES = 12_000

ALLOWED = {"path", "circle", "ellipse", "rect", "polygon", "polyline", "line", "g"}
GEOMETRY = {"d", "cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "points", "x1", "y1", "x2", "y2",
            "transform", "fill-rule", "clip-rule"}
WHITE = {"#fff", "#ffffff", "white", "none", "transparent"}


def fetch(url: str, cache: Path | None) -> bytes:
    if cache:
        hit = cache / hashlib.sha256(url.encode()).hexdigest()
        if hit.exists():
            return hit.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "readmefetch-vendor"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        hit.write_bytes(data)
    return data


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def style_fill(el) -> str:
    fill = el.get("fill", "")
    m = re.search(r"fill\s*:\s*([^;]+)", el.get("style", ""))
    return (m.group(1) if m else fill).strip().lower()


def hidden(el) -> bool:
    style = el.get("style", "")
    if re.search(r"display\s*:\s*none", style) or el.get("display") == "none":
        return True
    if el.get("opacity") in ("0", "0.0") or re.search(r"(?:^|;)\s*opacity\s*:\s*0(?:\.0*)?\s*(?:;|$)", style):
        return True
    return False


def shapes(el, out: list) -> None:
    """Copy drawable children of el, keeping geometry only; drop invisible and white (background) shapes."""
    for child in el:
        tag = local(child.tag)
        if tag not in ALLOWED or hidden(child):
            continue
        fill = style_fill(child)
        if tag != "g" and fill in WHITE and fill:
            continue
        attrs = {k: v for k, v in child.attrib.items() if k in GEOMETRY}
        fr = re.search(r"fill-rule\s*:\s*(\w+)", child.get("style", ""))
        if fr:
            attrs["fill-rule"] = fr.group(1)
        if tag == "g":
            inner: list = []
            shapes(child, inner)
            if inner:
                out.append(("g", attrs, inner))
        elif any(attrs.get(k) for k in ("d", "points", "r", "rx", "width")):
            out.append((tag, attrs, []))


def markup(nodes: list) -> str:
    parts = []
    for tag, attrs, kids in nodes:
        a = "".join(f' {k}="{v}"' for k, v in attrs.items())
        parts.append(f"<{tag}{a}>{markup(kids)}</{tag}>" if kids else f"<{tag}{a}/>")
    return "".join(parts)


def trim(markup_text: str, decimals: int) -> str:
    """Drop digits past `decimals` after a decimal point. Truncating never merges two numbers."""
    return re.sub(rf"(\d\.\d{{{decimals}}})\d+", r"\1", markup_text)


def from_svg(text: bytes) -> tuple[list[float], str]:
    root = ET.fromstring(text)
    vb = root.get("viewBox")
    if vb:
        box = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
    else:
        box = [0, 0, float(re.sub(r"[^\d.]", "", root.get("width"))), float(re.sub(r"[^\d.]", "", root.get("height")))]
    nodes: list = []
    shapes(root, nodes)
    if not nodes:
        raise ValueError("no shapes")
    return box, markup(nodes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, help="keep downloads here (handy while editing the lists)")
    args = ap.parse_args()
    cache = args.cache
    get = lambda url: fetch(url, cache)

    icons: dict[str, dict] = {}
    sources = {
        "octicons": {"name": "Octicons", "version": OCTICONS, "licence": "MIT", "url": "https://github.com/primer/octicons"},
        "simple-icons": {"name": "Simple Icons", "version": SIMPLE_ICONS, "licence": "CC0-1.0",
                         "url": "https://github.com/simple-icons/simple-icons"},
        "font-logos": {"name": "font-logos", "version": FONT_LOGOS, "licence": "Unlicense",
                       "url": "https://github.com/lukas-w/font-logos"},
        "devicon": {"name": "Devicon", "version": DEVICON, "licence": "MIT", "url": "https://github.com/devicons/devicon"},
    }

    oct_data = json.loads(get(f"{JSDELIVR}/@primer/octicons@{OCTICONS}/build/data.json"))
    for name in OCT:
        h16 = oct_data[name]["heights"]["16"]
        icons[f"oct-{name}"] = {"src": "octicons", "name": name, "box": [0, 0, h16["width"], 16], "svg": h16["path"]}

    si_meta = {i["slug"]: i for i in json.loads(get(f"{JSDELIVR}/simple-icons@{SIMPLE_ICONS}/data/simple-icons.json"))}
    dev_meta = {d["name"]: d for d in json.loads(get(f"{JSDELIVR}/devicon@{DEVICON}/devicon.json"))}
    si_free, swapped, dropped = [], {}, []  # swapped: Simple Icons slug -> Devicon name
    for slug in SI:
        licence = (si_meta[slug].get("license") or {}).get("type", "CC0-1.0")
        if licence in SI_FREE:
            si_free.append(slug)
        elif SI_TO_DEV.get(slug, slug) in dev_meta:
            swapped[slug] = SI_TO_DEV.get(slug, slug)
        else:
            dropped.append(f"{slug} ({licence})")
    if dropped:
        print(f"left out (own licence, not in Devicon): {', '.join(dropped)}", file=sys.stderr)
    dev_names = list(dict.fromkeys([*DEV, *swapped.values()]))

    def si_icon(slug):
        box, body = from_svg(get(f"{JSDELIVR}/simple-icons@{SIMPLE_ICONS}/icons/{slug}.svg"))
        return slug, {"src": "simple-icons", "name": slug, "title": si_meta[slug]["title"], "hex": "#" + si_meta[slug]["hex"],
                      "box": box, "svg": trim(body, 2)}

    tsv = get(f"{RAW}/lukas-w/font-logos/{FONT_LOGOS}/icons.tsv").decode()
    fl_names = [line.split("\t")[-1].strip() for line in tsv.splitlines()[1:] if line.strip()]

    def fl_icon(name):
        box, body = from_svg(get(f"{RAW}/lukas-w/font-logos/{FONT_LOGOS}/vectors/{name}.svg"))
        return name, {"src": "font-logos", "name": name, "box": box, "svg": trim(body, 1)}

    titles = {dev: si_meta[slug]["title"] for slug, dev in swapped.items()}

    def dev_icon(name):
        versions = dev_meta[name]["versions"]["svg"]
        version = "plain" if "plain" in versions else "original"
        box, body = from_svg(get(f"{JSDELIVR}/devicon@{DEVICON}/icons/{name}/{name}-{version}.svg"))
        icon = {"src": "devicon", "name": name, "hex": dev_meta[name].get("color", ""), "box": box, "svg": trim(body, 2)}
        if name in titles:
            icon["title"] = titles[name]
        return name, icon

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for slug, icon in pool.map(si_icon, si_free):
            icons[f"si-{slug}"] = icon
        for name, icon in pool.map(fl_icon, [n for n in fl_names if n not in FL_SKIP]):
            icons[f"linux-{name}"] = icon
        for name, icon in pool.map(dev_icon, dev_names):
            icons[f"dev-{name}"] = icon
    for key, icon in list(icons.items()):
        if len(icon["svg"]) > MAX_BYTES:
            print(f"skipping {key}: {len(icon['svg'])} bytes of shapes", file=sys.stderr)
            del icons[key]

    # Short names: Octicons first, then Simple Icons, font-logos and Devicon fill the gaps.
    short: dict[str, str] = {}
    for prefix in ("oct-", "si-", "linux-", "dev-"):
        for key in icons:
            if key.startswith(prefix):
                short.setdefault(key[len(prefix):], key)
    for slug, dev in swapped.items():  # the Simple Icons slug still works: :gnubash:, :vuedotjs:
        if f"dev-{dev}" in icons:
            short.setdefault(slug, f"dev-{dev}")
    for alias, target in ALIASES.items():
        if target in short and alias not in short:
            short[alias] = short[target]

    # Nerd Font names: exact for nf-oct-*, nf-linux-* and nf-dev-*, and by name for the rest.
    glyphs = json.loads(get(f"{RAW}/ryanoasis/nerd-fonts/{NERD_FONTS}/glyphnames.json"))
    glyphs.pop("METADATA", None)
    nerd: dict[str, str] = {}
    codepoint: dict[str, tuple] = {}  # key -> (rank, code): the glyph from the icon's own set wins
    rank_of = {"oct": 1, "linux": 1, "dev": 2, "md": 3, "fa": 4, "fae": 5, "seti": 6, "custom": 7, "cod": 8}
    for gname, g in glyphs.items():
        prefix, _, rest = gname.partition("-")
        key = None
        if prefix == "oct" and f"oct-{rest}" in icons:
            key = f"oct-{rest}"
        elif prefix == "linux" and f"linux-{rest}" in icons:
            key = f"linux-{rest}"
        else:
            stem = rest.removeprefix("language_").replace("_", "-")
            key = short.get(stem) or short.get(stem.replace("-", ""))
        if key:
            nerd[f"nf-{gname}"] = key
            rank = 0 if key.startswith(prefix + "-") else rank_of.get(prefix, 9)
            if key not in codepoint or rank < codepoint[key][0]:
                codepoint[key] = (rank, g["code"])
    for key, icon in icons.items():
        if key in codepoint:
            icon["nf"] = codepoint[key][1]

    OUT.mkdir(parents=True, exist_ok=True)
    data = {"sources": sources, "icons": icons, "short": dict(sorted(short.items())), "nerd": dict(sorted(nerd.items()))}
    (OUT / "icons.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n")
    (OUT / "LICENSE.octicons").write_bytes(get(f"{JSDELIVR}/@primer/octicons@{OCTICONS}/LICENSE"))
    (OUT / "LICENSE.simple-icons").write_bytes(get(f"{JSDELIVR}/simple-icons@{SIMPLE_ICONS}/LICENSE.md"))
    (OUT / "DISCLAIMER.simple-icons").write_bytes(get(f"{JSDELIVR}/simple-icons@{SIMPLE_ICONS}/DISCLAIMER.md"))
    (OUT / "LICENSE.font-logos").write_bytes(get(f"{RAW}/lukas-w/font-logos/{FONT_LOGOS}/LICENSE"))
    (OUT / "LICENSE.devicon").write_bytes(get(f"{JSDELIVR}/devicon@{DEVICON}/LICENSE"))
    (OUT / "LICENSE.nerd-fonts").write_bytes(get(f"{RAW}/ryanoasis/nerd-fonts/{NERD_FONTS}/LICENSE"))
    size = (OUT / "icons.json").stat().st_size
    print(f"wrote {len(icons)} icons, {len(short)} short names, {len(nerd)} Nerd Font names ({size / 1024:.0f} KiB)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
