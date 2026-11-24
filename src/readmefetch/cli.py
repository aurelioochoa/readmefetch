"""Command line: readmefetch [init|render|gif|print|web|logos|themes]."""

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from . import HOMEPAGE, __version__, badges, config, frames, icons, logos, stats, svg, term
from .themes import THEMES, palette


def _values(cfg, offline: bool) -> dict:
    needed = cfg.needed_stats()
    numbers = stats.fetch(cfg.github, needed) if needed and not offline else stats.offline(needed)
    return config.values(cfg, numbers, dt.date.today())


def _context(args):
    cfg = config.load(args.config)
    vals = _values(cfg, args.offline)
    return cfg, config.info_rows(cfg, vals), palette(cfg.theme, cfg.colors), vals


def write_badges(cfg, pal, vals: dict) -> list[Path]:
    paths = []
    if cfg.badges:
        cfg.badge_dir.mkdir(parents=True, exist_ok=True)
    for b in config.badges_for(cfg, vals):
        path = cfg.badge_dir / b.file
        path.write_text(badges.render(b, pal, cfg.window.style), encoding="utf-8")
        paths.append(path)
    return paths


def cmd_render(args) -> int:
    cfg, rows, pal, vals = _context(args)
    out = Path(args.output) if args.output else (cfg.path.parent / cfg.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg.render(cfg, rows, cfg.load_logos(), pal)[0], encoding="utf-8")
    written = [out] + write_badges(cfg, pal, vals)
    print(f"readmefetch: wrote {out}" + (f" and {len(written) - 1} badge(s) in {cfg.badge_dir}" if len(written) > 1 else ""),
          file=sys.stderr)
    print("\n".join(str(p) for p in written))
    return 0


def cmd_badges(args) -> int:
    cfg = config.load(args.config)
    if not cfg.badges:
        print("readmefetch: no [[badge]] tables in the config; see `readmefetch badges --help`", file=sys.stderr)
        return 1
    pal = palette(cfg.theme, cfg.colors)
    has_numbers = any(config.placeholders_in(b.label + b.message) for b in cfg.badges)
    paths = write_badges(cfg, pal, _values(cfg, args.offline) if has_numbers else config.values(cfg, {}, dt.date.today()))
    print(f"readmefetch: wrote {len(paths)} badge(s) in {cfg.badge_dir}. Paste this into your README:\n", file=sys.stderr)
    sys.stdout.write(badges.snippet(cfg.badges, cfg.badge_defaults["dir"], html=args.html))
    return 0


def cmd_gif(args) -> int:
    from . import gif

    cfg, rows, pal, _ = _context(args)
    text, meta = svg.render(cfg, rows, cfg.load_logos(), pal)
    out = Path(args.output) if args.output else (cfg.path.parent / cfg.output).with_suffix(".gif")
    report = gif.export(text, meta, out, fps=args.fps, scale=args.scale, intro=not args.no_intro,
                        frames_dir=Path(args.frames) if args.frames else None)
    print(f"readmefetch: wrote {out} ({report['frames']} frames, {report['seconds']:.1f}s, "
          f"{report['bytes'] / 1024:.0f} KiB)", file=sys.stderr)
    print(out)
    return 0


def _use_color(args) -> bool:
    if args.color == "always":
        return True
    if args.color == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def cmd_print(args) -> int:
    cfg, rows, pal, _ = _context(args)
    all_logos = cfg.load_logos()
    if args.logo:
        chosen = [logos.load(args.logo, cfg.logo_context())]
    else:
        chosen = all_logos[:1]
    sys.stdout.write(term.render(cfg, rows, chosen[0] if chosen else None, pal, _use_color(args), nerd_font=args.nerd_font))
    return 0


def cmd_icons(args) -> int:
    items = icons.catalog()
    term_ = " ".join(args.search).lower()
    if term_:
        items = [i for i in items if term_ in i["name"] or term_ in i["title"].lower() or term_ in i["nerd"]
                 or any(term_ in a for a in i["aliases"])]
    if not items:
        print(f"readmefetch: no icon matches {term_!r}", file=sys.stderr)
        return 1
    group = None
    for i in items:
        if i["group"] != group:
            group = i["group"]
            print(f"\n{group}")
        glyph = icons.glyph(i["key"]) if args.nerd_font else ""
        also = "".join(f" :{a}:" for a in i["aliases"])
        nerd = f"  :{i['nerd']}:" if i["nerd"] else ""
        print(f"  {glyph + ' ' if glyph else ''}:{i['name']}:{also}{nerd}")
    print("\nWrite them in info lines like \":repo: Repos: {repos}\", or as a badge's `icon`. Credits: CREDITS.md.")
    return 0


def cmd_windows(args) -> int:
    for name, note in frames.STYLES.items():
        preset = frames.PRESETS.get(name)
        extra = f"  (preset: {preset['theme']}, prompt {preset['prompt']!r})" if preset else ""
        print(f"{name:<9} {note}{extra}")
    return 0


def cmd_logos(args) -> int:
    pal = palette(args.theme)
    color = _use_color(args)
    if not args.names:
        rows = logos.catalog()
        width = max(len(n) for n, _ in rows)
        for name, source in rows:
            print(f"{name.ljust(width)}  {source}")
        print("\nPreview with `readmefetch logos NAME...`; every logo's full credit is shown there and in CREDITS.md.")
        return 0
    for name in args.names:
        lg = logos.load(name, {"initials": "RF", "user": "readmefetch"})
        still = lg.still()
        width = max((len(r) for r in still), default=0)
        print("\n".join(term.grid_lines(still, width, pal, color)))
        print(f"{lg.name}: {lg.credit}\n")
    return 0


def cmd_themes(args) -> int:
    color = _use_color(args)
    names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    for name in THEMES:
        pal = palette(name)
        swatch = "".join(f"{term.bg(pal[p + c])}  " for p in ("", "bright-") for c in names) + term.RESET if color else ""
        print(f"{name:<18} {swatch}")
    return 0


def cmd_web(args) -> int:
    from . import web

    return web.serve(Path(args.config), port=args.port, open_browser=args.open, verbose=args.verbose)


def cmd_init(args) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        print(f"readmefetch: {path} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    fields = {
        "user": "you", "host": "github", "lang": "python", "since": dt.date.today().isoformat(),
        "bio": "Software Developer", "location": "Earth", "blog": "you@example.com",
        "github_line": '# github = "your-username"     # enables {repos} {stars} {graph} and the other GitHub lines',
        "github_info": "",
    }
    if args.github:
        p = stats.profile(args.github)
        fields.update(
            user=args.github.lower(),
            since=(p.get("created_at") or fields["since"])[:10],
            bio=(p.get("bio") or "Software Developer").strip().replace('"', "'"),
            location=(p.get("location") or "Earth").replace('"', "'"),
            blog=(p.get("blog") or p.get("html_url") or "").replace('"', "'"),
            github_line=f'github = "{args.github}"',
            github_info='  ":mark-github: GitHub: {repos} repos · {stars} stars · {followers} followers",\n',
        )
    path.write_text(config.TEMPLATE.format(**fields), encoding="utf-8")
    print(f"readmefetch: wrote {path}. Edit it, then run `readmefetch print` or `readmefetch render`.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="readmefetch",
        description="An animated, neofetch-style terminal for your GitHub profile README.",
        epilog=f"Docs: {HOMEPAGE}",
    )
    p.add_argument("--version", action="version", version=f"readmefetch {__version__}")
    sub = p.add_subparsers(dest="command")

    def common(sp, stats_opt=True):
        sp.add_argument("-c", "--config", default=config.DEFAULT_PATH, help="config file (default: %(default)s)")
        if stats_opt:
            sp.add_argument("--offline", action="store_true", help="skip the GitHub API; live numbers show as 0")

    def colour(sp):
        sp.add_argument("--color", choices=["auto", "always", "never"], default="auto")

    sp = sub.add_parser("init", help="write a starter readmefetch.toml")
    common(sp, stats_opt=False)
    sp.add_argument("--github", metavar="USER", help="prefill from this GitHub profile")
    sp.add_argument("--force", action="store_true", help="overwrite an existing file")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("render", help="write the animated SVG")
    common(sp)
    sp.add_argument("-o", "--output", help="SVG path (default: `output` in the config)")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("gif", help="export the animation as a GIF (needs Chrome/Chromium/Brave/Edge and Pillow)")
    common(sp)
    sp.add_argument("-o", "--output", help="GIF path (default: `output` in the config, as .gif)")
    sp.add_argument("--fps", type=float, default=10, help="frames per second (default: %(default)s)")
    sp.add_argument("--scale", type=float, default=1.0, help="pixel density, e.g. 2 for sharper text (default: 1)")
    sp.add_argument("--no-intro", action="store_true", help="skip the typing intro so the GIF loops seamlessly")
    sp.add_argument("--frames", metavar="DIR", help="also save every frame as a PNG here")
    sp.set_defaults(func=cmd_gif)

    sp = sub.add_parser("print", help="show it in this terminal")
    common(sp)
    colour(sp)
    sp.add_argument("--logo", help="show this logo instead of the first one")
    sp.add_argument("--nerd-font", action="store_true", help="print :icons: as Nerd Font glyphs (needs a Nerd Font)")
    sp.set_defaults(func=cmd_print)

    sp = sub.add_parser("badges", help="write the [[badge]] SVGs and print the README lines that show them",
                        description="Badges are [[badge]] tables in the config (label, message, link, color, icon, style); "
                                    f"styles: {', '.join(badges.STYLES)}; icons: {', '.join(badges.ICONS)}, any name from "
                                    "`readmefetch icons`, or a 24x24 SVG path. Label and message can use {stars}, "
                                    "{followers} and the other live numbers.")
    common(sp)
    sp.add_argument("--html", action="store_true", help="print <a><img></a> HTML instead of Markdown")
    sp.set_defaults(func=cmd_badges)

    sp = sub.add_parser("web", help="edit the config in a local web app with a live preview")
    common(sp, stats_opt=False)
    sp.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (default: %(default)s; 0 picks a free one)")
    sp.add_argument("--open", action="store_true", help="open it in your browser")
    sp.add_argument("--verbose", action="store_true", help="log every request")
    sp.set_defaults(func=cmd_web)

    sp = sub.add_parser("logos", help="list built-in logos, or preview some")
    sp.add_argument("names", nargs="*")
    sp.add_argument("--theme", default="github-dark", choices=list(THEMES))
    colour(sp)
    sp.set_defaults(func=cmd_logos)

    sp = sub.add_parser("themes", help="list colour themes")
    colour(sp)
    sp.set_defaults(func=cmd_themes)

    sp = sub.add_parser("icons", help="list the icons for info lines and badges, or search them")
    sp.add_argument("search", nargs="*", help="part of a name, e.g. python or nf-oct")
    sp.add_argument("--nerd-font", action="store_true", help="show each icon's Nerd Font glyph too")
    sp.set_defaults(func=cmd_icons)

    sp = sub.add_parser("windows", help="list the window styles for [window] style")
    sp.set_defaults(func=cmd_windows)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        if Path(config.DEFAULT_PATH).exists():
            args = parser.parse_args(["print", *(argv or [])])
        else:
            parser.print_help()
            return 0
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"readmefetch: {e}", file=sys.stderr)
        return 1
    except OSError as e:  # network errors from the GitHub API
        print(f"readmefetch: {e}", file=sys.stderr)
        return 1
