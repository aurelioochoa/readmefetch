"""Render the terminal as an animated SVG.

GitHub shows README images through <img>, which runs CSS animations but no
scripts and cannot load web fonts. So everything here is CSS keyframes, and text
sits on an explicit character grid (every glyph gets its own x) so ASCII art lines
up whichever monospace font the viewer has. Without animation support, or with
reduced motion requested, the SVG shows a finished, static frame.

The first visit: the command types itself, then the output appears according to
[intro]. Covers in the background colour sit over each line (or column) and shrink
one character at a time, each at its own speed. With scope "all" the first logo is
typed too, so the logo cycle starts after the intro, partway into the first logo's
turn (its usual entrance is skipped once).
"""

import random
import re
from xml.sax.saxutils import escape

from . import HOMEPAGE, __version__
from .logos import Logo
from .themes import resolve

FONT = 14
CW = FONT * 0.6  # cell width
LH = 20  # line height
PAD = 24
BAR = 36  # title bar
ASCENT = 15  # cell top sits this far above the baseline
FONTS = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Cascadia Mono", '
         '"Liberation Mono", "DejaVu Sans Mono", monospace')
BLOCK_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]


def n(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def pct(x: float) -> str:
    return f"{min(max(x, 0), 100):.3f}".rstrip("0").rstrip(".") + "%"


def runs(row):
    """Contiguous same-colour glyphs: [(col, text, colour)]."""
    out = []
    for c, cell in enumerate(row):
        if cell is None:
            continue
        ch, color = cell
        if out and out[-1][2] == color and out[-1][0] + len(out[-1][1]) == c:
            out[-1] = (out[-1][0], out[-1][1] + ch, color)
        else:
            out.append((c, ch, color))
    return out


def grid_svg(grid, x0: float, y0: float, pal: dict) -> str:
    """y0 is the baseline of the grid's first row."""
    parts = []
    for r, row in enumerate(grid):
        for col, text, color in runs(row):
            xs = " ".join(n(x0 + (col + i) * CW) for i in range(len(text)))
            parts.append(f'<text x="{xs}" y="{n(y0 + r * LH)}" fill="{resolve(color, pal)}">{escape(text)}</text>')
    return "".join(parts)


def line_svg(segments, x0: float, y: float, pal: dict) -> str:
    """One line on the character grid. segments: (text, colour, css class); spaces are glyphs too."""
    parts, col = [], 0
    for text, color, cls in segments:
        if text.strip():
            xs = " ".join(n(x0 + (col + i) * CW) for i in range(len(text)))
            c = f' class="{cls}"' if cls else ""
            parts.append(f'<text x="{xs}" y="{n(y)}"{c} fill="{resolve(color, pal)}">{escape(text)}</text>')
        col += len(text)
    return "".join(parts)


class Css:
    def __init__(self):
        self.rules: list[str] = []

    def keyframes(self, name: str, frames: list[tuple]) -> None:
        """frames: (percent, declarations[, timing function for the segment that starts here])."""
        body, seen = [], set()
        for f in frames:
            p = pct(f[0])
            if p in seen:
                continue
            seen.add(p)
            decl = f[1] + (f"; animation-timing-function: {f[2]}" if len(f) > 2 and f[2] else "")
            body.append(f"{p} {{ {decl} }}")
        self.rules.append(f"@keyframes {name} {{ {' '.join(body)} }}")

    def rule(self, text: str) -> None:
        self.rules.append(text)


def window_slot(start: float, end: float) -> list[tuple]:
    """Opacity keyframes (use with step-end) that show an element during [start%, end%)."""
    frames = [] if start <= 0 else [(0, "opacity: 0")]
    frames.append((start, "opacity: 1"))
    frames += [(end, "opacity: 0"), (100, "opacity: 0")] if end < 100 else [(100, "opacity: 1")]
    return frames


def rotate(frames: list[tuple], shift: float, held: bool = False) -> list[tuple]:
    """The same looping keyframes, started `shift` percent into the loop.

    `held`: the rule's own timing function is step-end, so every segment holds its
    start value. The cut must fall on a keyframe or inside a held segment.
    """
    if shift <= 0:
        return frames
    fs = sorted(frames, key=lambda f: f[0])
    if fs[0][0] > 0 or fs[-1][0] < 100:
        raise ValueError("rotate() needs keyframes at 0% and 100%")
    shift = next((f[0] for f in fs if abs(f[0] - shift) < 1e-6), shift)  # land exactly on a keyframe
    i = max(j for j, f in enumerate(fs) if f[0] <= shift)
    cur = fs[i]
    timing = cur[2] if len(cur) > 2 else None
    if cur[0] != shift and not (held or timing == "step-end" or cur[1] == fs[i + 1][1]):
        raise ValueError("rotate() can't cut an animated segment")
    out = [(0, cur[1], timing)]
    out += [(f[0] - shift, *f[1:]) for f in fs if shift < f[0] < 100]
    end, start = fs[-1], fs[0]  # 100% and 0% meet again at 100 - shift
    if end[1] != start[1]:
        out.append((100 - shift - 0.001, end[1], "step-end"))
    out += [(f[0] + 100 - shift, *f[1:]) for f in fs if f[0] < shift]
    out.append((100, cur[1]))
    return out


def prompt_segments(cfg, pal: dict) -> list[tuple]:
    """The prompt as (text, colour, class) segments; {user}@{host} and {cwd} are bold and coloured."""
    vals = cfg.prompt_values()
    fmt = cfg.prompt.format.replace("{user}@{host}", "{title}")
    segs = []
    for part in re.split(r"(?<!\{)(\{(?:title|user|host|cwd)\})(?!\})", fmt):
        if not part:
            continue
        if part == "{title}":
            segs.append((f"{vals['user']}@{vals['host']}", cfg.prompt.user_color, "b"))
        elif part in ("{user}", "{host}"):
            segs.append((vals[part[1:-1]], cfg.prompt.user_color, "b"))
        elif part == "{cwd}":
            segs.append((vals["cwd"], cfg.prompt.cwd_color, "b"))
        else:
            segs.append((part.replace("{{", "{").replace("}}", "}"), "fg", ""))
    return segs


def cursor_rect(cfg, x: float, baseline: float, pal: dict, cls: str) -> str:
    style = cfg.cursor.style
    if style == "bar":
        geo = f'x="{n(x)}" y="{n(baseline - ASCENT + 2)}" width="2" height="{LH - 3}"'
    elif style == "underline":
        geo = f'x="{n(x)}" y="{n(baseline + 2)}" width="{n(CW)}" height="2"'
    else:
        geo = f'x="{n(x)}" y="{n(baseline - ASCENT + 2)}" width="{n(CW)}" height="{LH - 3}"'
    return f'<rect class="{cls}" {geo} fill="{resolve(cfg.cursor.color, pal)}"/>'


def entrance_seconds(lg: Logo, seconds_per_logo: float, art_h: int) -> float:
    """How long a logo's entrance takes (the part `scope = "all"` skips for the first logo)."""
    if lg.enter == "print":
        return min(max(art_h, 1) * 0.05, seconds_per_logo / 3)
    return min(0.7, seconds_per_logo / 4)


def layers_svg(lg: Logo, k: int, ox: float, oy: float, delay: float, pal: dict, css: Css) -> str:
    """A logo's still base plus its animated layers, each frame shown in turn."""
    out = [grid_svg(lg.base(), ox, oy, pal)]
    for j, layer in enumerate(lg.layers):
        total = sum(layer.weights)
        start = 0.0
        for i, (frame, w) in enumerate(zip(layer.frames, layer.weights)):
            end = start + 100 * w / total
            cls = f"rf-l{k}-{j}-{i}"
            if len(layer.frames) > 1:
                css.rule(f".{cls} {{ animation: {cls} {layer.period:.2f}s {delay:.2f}s infinite step-end; }}")
                css.keyframes(cls, window_slot(start, end))
            out.append(f'<g class="{cls}" opacity="{1 if i == 0 else 0}">'
                       f"{grid_svg(frame, ox + layer.col * CW, oy + layer.row * LH, pal)}</g>")
            start = end
    return "".join(out)


BOB = ".rf-bob { animation: rf-bob 1.4s ease-in-out infinite alternate; }"
BOB_FRAMES = [(0, "transform: translateY(1px)"), (100, "transform: translateY(-4px)")]


def render(cfg, rows: list, logos: list[Logo], pal: dict) -> tuple[str, dict]:
    """-> (svg text, timing: width, height, intro seconds, period seconds of the logo cycle)."""
    css = Css()
    title = cfg.title
    cmd = cfg.command
    intro = cfg.intro
    prompt = prompt_segments(cfg, pal)
    prompt_len = sum(len(s[0]) for s in prompt)
    win_title = cfg.window_title()

    # ---- layout --------------------------------------------------------------------
    art_w = max((lg.width for lg in logos), default=0)
    art_h = max((lg.height for lg in logos), default=0)
    info_col = art_w + 3 if logos else 0
    info_x = PAD + info_col * CW
    user, _, host = title.partition("@")
    key_cls = "b rf-key"
    lines: list = [[(user, "accent", key_cls), ("@", "fg", ""), (host, "accent", key_cls)],
                   [("-" * len(title), "dim", "")]]
    for r in rows:
        if r is None:
            lines.append([])
        elif r[0]:
            lines.append([(r[0], "accent", key_cls), (": " + r[1], "fg", "")])
        else:
            lines.append([(r[1], "fg", "")])
    if cfg.color_blocks:
        lines += [[], "blocks", "bright-blocks"]

    def line_len(line) -> int:
        return 24 if isinstance(line, str) else sum(len(s[0]) for s in line)

    width = round(max(info_x + max(line_len(x) for x in lines) * CW + PAD,
                      2 * PAD + (prompt_len + len(cmd) + 2) * CW,
                      (len(win_title) * 7.2 + 150) if win_title else 0, 320))
    total_rows = max(art_h, len(lines))
    y0 = BAR + 30  # baseline of the command line
    body_y = y0 + 2 * LH  # baseline of the first output row
    final_y = body_y + total_rows * LH + LH
    height = round(final_y + PAD)

    # ---- timing (seconds) ----------------------------------------------------------
    t_type = 0.4
    type_dur = max(0.3, len(cmd) / intro.command_speed) if cmd else 0
    t_out = t_type + type_dur + 0.35
    period = cfg.seconds_per_logo * max(len(logos), 1)
    first = logos[0] if logos else None
    f_ox = (art_w - first.width) // 2 if first else 0
    f_oy = (art_h - first.height) // 2 if first else 0

    # the intro: what is covered, and how each line (or column) is uncovered
    reveal = []  # (x, y, w, h, origin, keyframes, steps, delay, duration)
    if intro.scope == "none":
        t_end = t_out + total_rows * 0.04
    else:
        cells: set[tuple[int, int]] = set()
        for r, line in enumerate(lines):
            cells.update((r, info_col + c) for c in range(line_len(line)))
        if intro.scope == "all" and first:
            for r, row in enumerate(first.still()):
                cells.update((f_oy + r, f_ox + c) for c, cell in enumerate(row) if cell)
        units = {}  # line (row or column) -> [first, last] along the direction
        for r, c in cells:
            lane, pos = (r, c) if intro.horizontal else (c, r)
            lo, hi = units.get(lane, (pos, pos))
            units[lane] = (min(lo, pos), max(hi, pos))
        rng = random.Random(intro.seed)
        base = min(units) if units else 0
        t_end = t_out
        for lane in sorted(units):
            lo, hi = units[lane]
            count = hi - lo + 1
            speed = intro.cells_per_second * max(0.15, 1 + intro.variance * (2 * rng.random() - 1))
            dur = count / speed
            delay = t_out + (lane - base) * intro.gap
            t_end = max(t_end, delay + dur)
            if intro.horizontal:
                x, y, w, h = PAD + lo * CW, body_y + lane * LH - ASCENT, count * CW, LH
                origin = (x + w, y) if intro.direction == "left-to-right" else (x, y)
                reveal.append((x, y, w, h, origin, "rf-rx", count, delay, dur))
            else:
                x, y, w, h = PAD + lane * CW, body_y + lo * LH - ASCENT, CW + 0.5, count * LH
                origin = (x, y + h) if intro.direction == "top-to-bottom" else (x, y)
                reveal.append((x, y, w, h, origin, "rf-ry", count, delay, dur))
    typed_art = intro.scope == "all" and first is not None
    cycle_at = t_end if typed_art else t_out  # when the logo cycle starts
    shift = 100 * entrance_seconds(first, cfg.seconds_per_logo, art_h) / period if typed_art else 0

    def cycle(frames, held=False):
        return rotate(frames, shift, held)

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
      f'role="img" aria-labelledby="rf-title rf-desc">')
    a(f"<!-- Generated by readmefetch {__version__} ({HOMEPAGE}) -->")
    credits = []
    for lg in logos:
        if lg.credit:
            credits.append(f"{lg.name}: {lg.credit}")
            a(f"<!-- Logo '{escape(lg.name)}': {escape(lg.credit).replace('--', '-')} -->")
    a(f'<title id="rf-title">{escape(title)}: {escape(cmd)}</title>')
    desc = "; ".join(f"{r[0]}: {r[1]}" if r[0] else r[1] for r in rows if r)
    if credits:
        desc += ". Logo credits: " + "; ".join(credits)
    a(f'<desc id="rf-desc">{escape(desc)}</desc>')
    style_at = len(out)  # the <style> element goes here once all rules are known

    css.rule(f"text {{ font-family: {FONTS}; font-size: {FONT}px; white-space: pre; }}")
    css.rule(".b, .art text { font-weight: 700; }")
    css.rule(".ln { animation: rf-show .12s ease-out backwards; }")
    css.keyframes("rf-show", [(0, "opacity: 0"), (100, "opacity: 1")])

    # ---- window ------------------------------------------------------------------
    a(f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10" fill="{pal["bg"]}" stroke="{pal["border"]}"/>')
    a(f'<path d="M.5 {BAR}V10.5a10 10 0 0 1 10-10h{width - 21}a10 10 0 0 1 10 10V{BAR}z" fill="{pal["bar"]}"/>')
    a(f'<line x1=".5" y1="{BAR}" x2="{width - .5}" y2="{BAR}" stroke="{pal["border"]}"/>')
    if cfg.window.buttons:
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
            a(f'<circle cx="{20 + i * 20}" cy="{BAR / 2}" r="6" fill="{c}"/>')
    if win_title:
        a(f'<text x="{width / 2}" y="{BAR / 2 + 4.5}" fill="{pal["dim"]}" text-anchor="middle" style="font-size:12px">'
          f"{escape(win_title)}</text>")

    # ---- the command, typed --------------------------------------------------------
    cmd_x = PAD + prompt_len * CW
    cmd_w = len(cmd) * CW
    a(line_svg(prompt, PAD, y0, pal))
    if cmd:
        a(grid_svg([[(ch, "fg") if ch != " " else None for ch in cmd]], cmd_x, y0, pal))
        a(f'<rect class="rf-cover" x="{n(cmd_x + cmd_w)}" y="{y0 - ASCENT}" width="{n(cmd_w + CW)}" height="{LH}" '
          f'fill="{pal["bg"]}"/>')
        steps = len(cmd)
        css.rule(f".rf-cover {{ animation: rf-type {type_dur:.2f}s steps({steps}, end) {t_type}s backwards; }}")
        css.keyframes("rf-type", [(0, f"transform: translateX(-{n(cmd_w)}px)"), (100, "transform: translateX(0)")])
        css.rule(f".rf-caret {{ opacity: 0; animation: rf-caret-on {t_out:.2f}s linear, "
                 f"rf-caret-move {type_dur:.2f}s steps({steps}, end) {t_type}s both; }}")
        css.keyframes("rf-caret-move", [(0, "transform: translateX(0)"), (100, f"transform: translateX({n(cmd_w)}px)")])
    else:
        css.rule(f".rf-caret {{ opacity: 0; animation: rf-caret-on {t_out:.2f}s linear; }}")
    a(cursor_rect(cfg, cmd_x, y0, pal, "rf-caret"))
    css.keyframes("rf-caret-on", [(0, "opacity: 1"), (99, "opacity: 1"), (100, "opacity: 0")])

    # ---- logos ---------------------------------------------------------------------
    if logos:
        clip_x, clip_y = PAD - CW, body_y - ASCENT - 6
        clip_w, clip_h = (art_w + 2) * CW, art_h * LH + 10
        a(f'<clipPath id="rf-art"><rect x="{n(clip_x)}" y="{n(clip_y)}" width="{n(clip_w)}" height="{n(clip_h)}"/></clipPath>')
        fade_in = "" if typed_art else f' style="animation-delay:{t_out:.2f}s"'
        a(f'<g class="{"art" if typed_art else "ln art"}"{fade_in} clip-path="url(#rf-art)">')
        count = len(logos)
        cyc = f"{period:.2f}s {cycle_at:.2f}s infinite"
        for k, lg in enumerate(logos):
            p0, p1 = 100 * k / count, 100 * (k + 1) / count
            ox = PAD + (art_w - lg.width) // 2 * CW
            oy = body_y + (art_h - lg.height) // 2 * LH
            ease = min(0.7 / period * 100, (p1 - p0) / 4)
            scene = f"rf-s{k}"
            if count > 1 and lg.enter != "fade":
                css.rule(f".{scene} {{ animation: {scene} {cyc} step-end; }}")
                css.keyframes(scene, cycle(window_slot(p0, p1), held=True))
            elif lg.enter == "fade":
                css.rule(f".{scene} {{ animation: {scene} {cyc} linear; }}")
                fr = [] if p0 <= 0 else [(0, "opacity: 0", "step-end")]
                fr += [(p0, "opacity: 0"), (p0 + ease, "opacity: 1"), (p1 - ease, "opacity: 1"), (p1, "opacity: 0")]
                fr += [(100, "opacity: 0")] if p1 < 100 else []
                css.keyframes(scene, cycle(fr))
            a(f'<g class="{scene}" opacity="{1 if k == 0 else 0}">')
            if lg.ground:
                a(grid_svg(lg.ground, ox, oy + lg.art_rows * LH, pal))
            mover = ""
            if lg.enter == "fly":
                mover = f"rf-m{k}"
                lift = f"transform: translateY(-{n(clip_h + LH)}px)"
                rest = "transform: translateY(0)"
                fr = [] if p0 <= 0 else [(0, lift, "step-end")]
                fr += [(p0, lift, "ease-out"), (p0 + ease, rest, "linear"), (p1 - ease, rest, "ease-in"), (p1, lift, "step-end")]
                fr += [(100, lift)] if p1 < 100 else []
                css.rule(f".{mover} {{ animation: {mover} {cyc}; }}")
                css.keyframes(mover, cycle(fr))
            a(f'<g class="{mover}">' if mover else "<g>")
            a('<g class="rf-bob">' if lg.hover else "<g>")
            a(layers_svg(lg, k, ox, oy, t_out, pal, css))
            a("</g></g>")
            if lg.enter == "print":
                cover = f"rf-c{k}"
                rows_n = max(art_h, 1)  # one step per row of the art area
                dur = 100 * entrance_seconds(lg, cfg.seconds_per_logo, art_h) / period
                up = f"transform: translateY(-{n(clip_h)}px)"
                fr = [] if p0 <= 0 else [(0, up, "step-end")]
                fr += [(p0, up, f"steps({rows_n}, end)"), (p0 + dur, "transform: translateY(0)", "step-end"),
                       (100, "transform: translateY(0)")]
                css.rule(f".{cover} {{ animation: {cover} {cyc}; }}")
                css.keyframes(cover, cycle(fr))
                a(f'<rect class="{cover}" x="{n(clip_x)}" y="{n(clip_y + clip_h)}" width="{n(clip_w)}" '
                  f'height="{n(clip_h)}" fill="{pal["bg"]}"/>')
            a("</g>")
        a("</g>")
        if any(lg.hover for lg in logos):
            css.rule(BOB)
            css.keyframes("rf-bob", BOB_FRAMES)

    # ---- info ----------------------------------------------------------------------
    accents = [resolve(lg.accent, pal) for lg in logos] or [pal["accent"]]
    if len(set(accents)) > 1:
        fr = [(100 * k / len(accents), f"fill: {c}") for k, c in enumerate(accents)] + [(100, f"fill: {accents[-1]}")]
        css.rule(f".rf-key {{ animation: rf-key {period:.2f}s {cycle_at:.2f}s infinite step-end; }}")
        css.keyframes("rf-key", cycle(fr, held=True))
    key_pal = dict(pal, accent=accents[0])
    for r, line in enumerate(lines):
        y = body_y + r * LH
        if isinstance(line, str):
            prefix = "" if line == "blocks" else "bright-"
            part = "".join(f'<rect x="{n(info_x + i * 3 * CW)}" y="{y - ASCENT + 1}" width="{n(3 * CW)}" '
                           f'height="{LH - (1 if line == "blocks" else 2)}" fill="{pal[prefix + c]}"/>'
                           for i, c in enumerate(BLOCK_NAMES))
        else:
            part = line_svg(line, info_x, y, key_pal)
        if part:
            fade = f' class="ln" style="animation-delay:{t_out + r * 0.04:.2f}s"' if intro.scope == "none" else ""
            a(f"<g{fade}>{part}</g>")

    # ---- the intro's covers (over everything they hide) ----------------------------
    if reveal:
        css.rule(".rf-rv { opacity: 0; }")
        css.keyframes("rf-rx", [(0, "opacity: 1; transform: scaleX(1)"), (100, "opacity: 1; transform: scaleX(0)")])
        css.keyframes("rf-ry", [(0, "opacity: 1; transform: scaleY(1)"), (100, "opacity: 1; transform: scaleY(0)")])
        a('<g shape-rendering="crispEdges">')  # no anti-aliased seams between neighbouring covers
        for x, y, w, h, (ox_, oy_), frames, steps, delay, dur in reveal:
            a(f'<rect class="rf-rv" x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" fill="{pal["bg"]}" opacity="0" '
              f'style="transform-origin:{n(ox_)}px {n(oy_)}px;'
              f'animation:{frames} {dur:.2f}s steps({steps},end) {delay:.2f}s both"/>')
        a("</g>")

    # ---- the next prompt, with a blinking cursor -----------------------------------
    a(f'<g class="ln" style="animation-delay:{t_end:.2f}s">{line_svg(prompt, PAD, final_y, pal)}</g>')
    a(cursor_rect(cfg, cmd_x, final_y, pal, "rf-cursor"))
    blink = (f", rf-blink {cfg.cursor.period:.2f}s step-end {t_end:.2f}s infinite" if cfg.cursor.blink else "")
    css.rule(f".rf-cursor {{ animation: rf-show .12s ease-out {t_end:.2f}s backwards{blink}; }}")
    if cfg.cursor.blink:
        css.keyframes("rf-blink", [(0, "opacity: 1"), (50, "opacity: 0"), (100, "opacity: 0")])
    css.rule("@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }")

    out.insert(style_at, "<style>\n" + "\n".join(css.rules) + "\n</style>")
    a("</svg>")
    intro_s = max(t_end, cycle_at)
    return "\n".join(out) + "\n", {"width": width, "height": height, "intro": intro_s, "period": period}


def render_logo(lg: Logo, pal: dict) -> tuple[str, dict]:
    """Just one logo, animated, on the terminal background (the web app's logo editor preview)."""
    css = Css()
    width = round((lg.width + 4) * CW)
    height = round((lg.height + 2) * LH)
    ox, oy = 2 * CW, LH + ASCENT - 4
    css.rule(f"text {{ font-family: {FONTS}; font-size: {FONT}px; white-space: pre; font-weight: 700; }}")
    body = layers_svg(lg, 0, ox, oy, 0, pal, css)
    if lg.ground:
        body += grid_svg(lg.ground, ox, oy + lg.art_rows * LH, pal)
    if lg.hover:
        css.rule(BOB)
        css.keyframes("rf-bob", BOB_FRAMES)
        body = f'<g class="rf-bob">{body}</g>'
    css.rule("@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f"<style>{' '.join(css.rules)}</style>"
           f'<rect width="{width}" height="{height}" rx="8" fill="{pal["bg"]}"/>{body}</svg>\n')
    return svg, {"width": width, "height": height}
