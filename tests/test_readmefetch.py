import contextlib
import datetime as dt
import io
import os
import re
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from readmefetch import cli, config, figlet, logos, svg, term  # noqa: E402
from readmefetch.themes import THEMES, palette, resolve  # noqa: E402

TODAY = dt.date(2026, 11, 24)


def make_config(**overrides) -> config.Config:
    data = {
        "user": "ada", "host": "engine", "logos": ["drone", "tux"],
        "info": ["OS: Analytical Engine", "Uptime: {uptime}", "", "a line without a key"],
        "uptime_since": dt.date(2021, 5, 1),
    }
    data.update(overrides)
    return config.from_dict(data)


def render(cfg: config.Config) -> tuple[str, dict]:
    vals = config.values(cfg, {}, TODAY)
    return svg.render(cfg, config.info_rows(cfg, vals), cfg.load_logos(), palette(cfg.theme, cfg.colors))


class Parsing(unittest.TestCase):
    def test_dollar_colours_are_sticky_and_dollar_dollar_is_literal(self):
        grid = logos.parse_dollar("$1ab\ncd$2e$$\n$9f", ["red", "blue"])
        self.assertEqual(grid[0], [("a", "red"), ("b", "red")])
        self.assertEqual(grid[1], [("c", "red"), ("d", "red"), ("e", "blue"), ("$", "blue")])
        self.assertEqual(grid[2], [("f", "blue")])  # $9 has no colour: ignored, like fastfetch

    def test_spaces_are_empty_cells_and_trailing_blank_rows_go(self):
        grid = logos.parse_dollar(" x \n\n", ["red"])
        self.assertEqual(grid, [[None, ("x", "red")]])

    def test_onefetch_braces(self):
        grid = logos.parse_braces("{0}a{1}b$", ["#111111", "#222222"])
        self.assertEqual(grid[0], [("a", "#111111"), ("b", "#222222"), ("$", "#222222")])


class Logos(unittest.TestCase):
    def test_every_builtin_logo_loads_and_is_credited(self):
        for name, _source in logos.catalog():
            with self.subTest(logo=name):
                lg = logos.load(name, {"initials": "AO", "user": "ada"})
                self.assertGreater(lg.width, 0)
                self.assertGreater(lg.height, 0)
                self.assertTrue(lg.credit, "every built-in logo must say where its art comes from")
                for layer in lg.layers:
                    self.assertEqual(len(layer.frames), len(layer.weights))
                    self.assertGreater(layer.period, 0)
                    for frame in layer.frames:
                        self.assertLessEqual(layer.row + len(frame), lg.art_rows)
                for row in lg.still():
                    for cell in row:
                        if cell:
                            resolve(cell[1], THEMES["github-dark"])  # every colour resolves

    def test_third_party_credits_name_the_artists_and_licences(self):
        self.assertIn("dixsept", logos.load("cauldron").credit)
        self.assertIn("aniwey", logos.load("computer").credit)
        self.assertIn("CC BY-SA 3.0", logos.load("computer").credit)
        self.assertIn("Dylan Araps", logos.load("linux").credit)
        self.assertIn("Ossama Hjaji", logos.load("python").credit)
        self.assertIn("Glenn Chappell", logos.load("banner", {"user": "x"}).credit)

    def test_vendored_licences_are_present(self):
        art = Path(logos.ART_DIR)
        for f in ["fastfetch/LICENSE", "fastfetch/LICENSE.neofetch", "onefetch/LICENSE", "candybox2/LICENSE.md",
                  "figlet/LICENSE", "figlet/LICENSE.tubes"]:
            self.assertTrue((art / f).is_file(), f)

    def test_layer_cells_are_removed_from_the_base_art(self):
        tux = logos.load("tux")
        layer = tux.layers[0]
        self.assertIsNone(tux.base()[layer.row][layer.col])
        self.assertEqual(tux.still()[layer.row][layer.col][0], "O")

    def test_initials_reach_the_drone(self):
        rows = ["".join(c[0] if c else " " for c in r) for r in logos.load("drone", {"initials": "XY"}).still()]
        self.assertTrue(any("( X Y )" in r for r in rows))

    def test_custom_logo(self):
        lg = logos.custom("mine", {"art": "$1/\\\n$2\\/", "colors": ["red", "#00ff00"], "enter": "fly",
                                   "layers": [{"row": 0, "col": 0, "frames": ["$1*", "$2+"], "period": 1}]})
        self.assertEqual(lg.art[1][0], ("\\", "#00ff00"))
        self.assertEqual(len(lg.layers[0].frames), 2)
        with self.assertRaises(ValueError):
            logos.custom("bad", {"art": "x", "enter": "teleport"})

    def test_unknown_logo(self):
        with self.assertRaises(ValueError):
            logos.load("no-such-logo")


class Figlet(unittest.TestCase):
    def test_fonts_render_without_hardblanks(self):
        for name in figlet.fonts():
            with self.subTest(font=name):
                font = figlet.load(name)
                lines = figlet.render("Hi!", font)
                self.assertTrue(lines)
                self.assertLessEqual(len(lines), font.height)
                self.assertNotIn(font.hardblank, "".join(lines))
                self.assertTrue(font.credit)

    def test_letters_fit_together(self):
        font = figlet.load("standard")
        wide = sum(max(len(r) for r in figlet.render(c, font)) for c in "readme")
        self.assertLess(max(len(r) for r in figlet.render("readme", font)), wide)


class Config(unittest.TestCase):
    def test_uptime(self):
        self.assertEqual(config.uptime(dt.date(2021, 5, 1), TODAY), "5 years, 6 months")
        self.assertEqual(config.uptime(dt.date(2026, 11, 1), TODAY), "0 months")
        self.assertEqual(config.uptime(dt.date(2025, 11, 24), TODAY), "1 year")
        self.assertEqual(config.uptime(dt.date(2027, 1, 1), TODAY), "not booted yet")

    def test_placeholders_and_rows(self):
        cfg = make_config(info=["Uptime: {uptime}", "", "no key here", "Braces: {{literal}}"])
        rows = config.info_rows(cfg, config.values(cfg, {}, TODAY))
        self.assertEqual(rows, [("Uptime", "5 years, 6 months"), None, ("", "no key here"), ("Braces", "{literal}")])

    def test_mistakes_are_reported(self):
        with self.assertRaises(ValueError):
            make_config(info=["{nope}"])
        with self.assertRaises(ValueError):
            config.from_dict({"info": ["{uptime}"]})
        with self.assertRaises(ValueError):
            config.from_dict({"info": ["{stars}"]})
        with self.assertRaises(ValueError):
            config.from_dict({"theme": "no-such-theme"})
        with self.assertRaises(ValueError):
            config.from_dict({"colour_blocks": True})  # typo of color_blocks

    def test_template_is_valid_toml(self):
        import tomllib
        text = config.TEMPLATE.format(user="u", host="h", lang="python", since="2020-01-01", bio="b", location="l",
                                      blog="w", github_line='github = "u"', github_info='  "GitHub: {repos}",\n')
        data = tomllib.loads(text)
        config.from_dict(data)


class Svg(unittest.TestCase):
    def test_well_formed_and_aligned(self):
        text, meta = render(make_config(logos=["drone", "tux", "cauldron", "computer", "banner", "python"]))
        xml.dom.minidom.parseString(text)
        self.assertGreater(meta["period"], 0)
        for m in re.finditer(r'<text x="([^"]+)"[^>]*>([^<]*)</text>', text):
            xs = m.group(1).split()
            if len(xs) > 1:
                glyphs = re.sub(r"&\w+;", "_", m.group(2))
                self.assertEqual(len(xs), len(glyphs), m.group(0)[:120])

    def test_credits_are_embedded(self):
        text, _ = render(make_config(logos=["computer", "linux"]))
        self.assertIn("aniwey", text)
        self.assertIn("CC BY-SA 3.0", text)
        self.assertIn("Dylan Araps", text)

    def test_reduced_motion_and_static_fallback(self):
        text, _ = render(make_config())
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn('class="rf-s0" opacity="1"', text)
        self.assertIn('class="rf-s1" opacity="0"', text)

    def test_no_logos(self):
        text, _ = render(make_config(logos=[]))
        xml.dom.minidom.parseString(text)

    def test_every_theme(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                xml.dom.minidom.parseString(render(make_config(theme=theme))[0])


class Terminal(unittest.TestCase):
    def test_plain_and_colour(self):
        cfg = make_config()
        rows = config.info_rows(cfg, config.values(cfg, {}, TODAY))
        pal = palette(cfg.theme)
        plain = term.render(cfg, rows, cfg.load_logos()[0], pal, color=False)
        self.assertNotIn("\x1b", plain)
        self.assertIn("ada@engine", plain)
        self.assertIn("Uptime: 5 years, 6 months", plain)
        self.assertIn("\x1b[", term.render(cfg, rows, cfg.load_logos()[0], pal, color=True))


class Cli(unittest.TestCase):
    def run_cli(self, *args) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_init_render_print(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "readmefetch.toml"
            self.assertEqual(self.run_cli("init", "-c", str(path))[0], 0)
            self.assertEqual(self.run_cli("init", "-c", str(path))[0], 1)  # refuses to overwrite
            code, out, err = self.run_cli("render", "-c", str(path), "--offline")
            self.assertEqual(code, 0, err)
            xml.dom.minidom.parse(out.strip())
            code, out, err = self.run_cli("print", "-c", str(path), "--offline", "--color", "never")
            self.assertEqual(code, 0, err)
            self.assertIn("you@github", out)

    def test_errors_are_messages_not_tracebacks(self):
        code, _, err = self.run_cli("render", "-c", "/nonexistent/readmefetch.toml")
        self.assertEqual(code, 1)
        self.assertIn("readmefetch init", err)

    def test_logos_and_themes(self):
        code, out, _ = self.run_cli("logos")
        self.assertEqual(code, 0)
        self.assertIn("cauldron", out)
        code, out, _ = self.run_cli("logos", "computer", "--color", "never")
        self.assertIn("aniwey", out)
        self.assertEqual(self.run_cli("themes", "--color", "never")[0], 0)


def _gif_tools() -> bool:
    try:
        import PIL  # noqa: F401

        from readmefetch.gif import find_browser
        find_browser()
        return os.name == "posix"
    except (ImportError, RuntimeError):
        return False


@unittest.skipUnless(_gif_tools(), "needs Pillow and a Chromium-family browser")
class Gif(unittest.TestCase):
    def test_frames_are_rendered_and_animated(self):
        from PIL import Image

        from readmefetch import gif

        text, meta = render(make_config(logos=["tux"], seconds_per_logo=2))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.gif"
            frames = Path(tmp) / "frames"
            report = gif.export(text, meta, out, fps=4, frames_dir=frames)
            self.assertGreater(report["sigma"], 5, "the last frame should not be blank")
            first = Image.open(frames / "frame-0000.png")
            last = Image.open(sorted(frames.iterdir())[-1])
            self.assertNotEqual(first.tobytes(), last.tobytes(), "the intro should change the picture")
            with Image.open(out) as im:
                self.assertGreater(getattr(im, "n_frames", 1), 1)
                self.assertEqual(im.size, (meta["width"], meta["height"]))


if __name__ == "__main__":
    unittest.main()
