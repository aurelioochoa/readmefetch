"""Tests for window styles, GitHub metrics and visuals, icons, the new badge styles and their web endpoints."""

import contextlib
import datetime as dt
import http.client
import io
import json
import sys
import tempfile
import threading
import unittest
import xml.dom.minidom
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from test_readmefetch import make_config  # noqa: E402

from readmefetch import badges, cli, config, frames, icons, rich, stats, svg, term, web  # noqa: E402
from readmefetch.themes import THEMES, palette  # noqa: E402

TODAY = dt.date(2026, 11, 24)


def full(cfg: config.Config, numbers: dict | None = None) -> tuple[str, dict, list, dict]:
    """Render with offline sample stats (plus `numbers`): (svg, meta, rows, values)."""
    pal = palette(cfg.theme, cfg.colors)
    sample = stats.offline(cfg.needed_stats(), TODAY)
    sample.update(numbers or {})
    vals = config.values(cfg, sample, TODAY, pal)
    rows = config.info_rows(cfg, vals)
    text, meta = svg.render(cfg, rows, cfg.load_logos(), pal)
    return text, meta, rows, vals


class Windows(unittest.TestCase):
    def test_every_style_renders(self):
        sizes = {}
        for style in frames.STYLES:
            with self.subTest(style=style):
                text, meta, _, _ = full(make_config(window={"style": style}))
                xml.dom.minidom.parseString(text)
                sizes[style] = (meta["width"], meta["height"])
                if style != "none":
                    self.assertIn("ada@engine", text)  # the default title
        self.assertLess(sizes["none"][1], sizes["macos"][1])  # no title bar
        self.assertLess(sizes["aqua"][1], sizes["tahoe"][1])

    def test_thumbnails(self):
        for style in frames.STYLES:
            with self.subTest(style=style):
                xml.dom.minidom.parseString(frames.thumbnail(style, palette("github-dark"), "Terminal"))

    def test_presets_are_valid_configs(self):
        for style, p in frames.PRESETS.items():
            with self.subTest(style=style):
                self.assertIn(p["theme"], THEMES)
                cfg = make_config(theme=p["theme"], window={"style": style, "title": p["title"]},
                                  prompt={"format": p["prompt"]}, cursor={"style": p["cursor"]})
                xml.dom.minidom.parseString(full(cfg)[0])

    def test_unknown_style(self):
        with self.assertRaisesRegex(ValueError, "style"):
            make_config(window={"style": "beos"})

    def test_buttons_can_be_hidden(self):
        with_buttons = full(make_config(window={"style": "win95"}))[0]
        without = full(make_config(window={"style": "win95", "buttons": False}))[0]
        self.assertGreater(len(with_buttons), len(without))


class Metrics(unittest.TestCase):
    def test_numbers_get_thousands_separators(self):
        cfg = make_config(github="ada", info=["Stars: {stars}", "Since: {joined}"])
        _, _, rows, vals = full(cfg, {"stars": 12345, "joined": "2014"})
        self.assertEqual(vals["stars"], "12,345")
        self.assertEqual(rows[0], ("Stars", "12,345"))
        self.assertEqual(rows[1], ("Since", "2014"))

    def test_github_placeholders_need_a_username(self):
        with self.assertRaisesRegex(ValueError, "github"):
            make_config(info=["PRs: {prs}"])
        self.assertEqual(make_config(github="ada", info=["{graph}", "{langbar}"]).needed_stats(),
                         {"calendar", "languages"})

    def test_visuals(self):
        cfg = make_config(github="ada", info=["Activity: {graph}", "{heatmap}", "Langs: {langbar}", "{languages}", "After"])
        text, meta, rows, vals = full(cfg)
        xml.dom.minidom.parseString(text)
        self.assertIsInstance(vals["graph"], list)
        self.assertEqual(rows[0][0][0].text, "Activity")  # key spans, then the bars
        self.assertTrue(any(isinstance(s, rich.Bars) for s in rows[0][1]))
        heat = rows.index(next(r for r in rows if r and any(isinstance(s, rich.Heat) for s in r[1])))
        self.assertEqual(rows[heat + 1:heat + rich.HEAT_ROWS], [None] * (rich.HEAT_ROWS - 1))
        self.assertEqual(rows[-1], ("", "After"))
        self.assertIn("clipPath", text)  # the language bar's rounded ends
        self.assertIn("Python", text)  # the legend
        weeks = make_config(github="ada", info=["{heatmap}"], metrics={"weeks": 10})
        self.assertEqual(full(weeks)[2][0][1][0].weeks.__len__(), 10)

    def test_visual_rules(self):
        with self.assertRaisesRegex(ValueError, "heatmap"):
            make_config(github="ada", info=["Activity: {heatmap} {stars}"])
        with self.assertRaisesRegex(ValueError, "badge"):
            make_config(github="ada", badge=[{"label": "Graph", "message": "{graph}"}])
        with self.assertRaises(ValueError):
            make_config(metrics={"weeks": 2})

    def test_literal_braces(self):
        _, _, rows, _ = full(make_config(info=["Code: {{not a placeholder}}"]))
        self.assertEqual(rows[0], ("Code", "{not a placeholder}"))

    def test_terminal_output(self):
        cfg = make_config(github="ada", info=["Activity: {graph}", "{heatmap}", ":python: Py: yes"])
        pal = palette(cfg.theme)
        vals = config.values(cfg, stats.offline(cfg.needed_stats(), TODAY), TODAY, pal)
        rows = config.info_rows(cfg, vals)
        plain = term.render(cfg, rows, None, pal, color=False)
        self.assertTrue(set(plain) & set(term.SPARK[1:]))
        self.assertIn("▀", term.render(cfg, rows, None, pal, color=True))
        self.assertNotIn(icons.glyph("si-python"), plain)
        self.assertIn(icons.glyph("si-python"), term.render(cfg, rows, None, pal, color=False, nerd_font=True))

    def test_streaks(self):
        day = lambda i, n: ((TODAY - dt.timedelta(days=i)).isoformat(), n, 1 if n else 0)  # noqa: E731
        days = [day(i, n) for i, n in zip(range(9, -1, -1), [1, 1, 1, 0, 2, 3, 0, 1, 1, 0])]
        self.assertEqual(stats.streaks(days, TODAY), (2, 3))  # nothing yet today: yesterday's run counts
        days[-1] = day(0, 4)
        self.assertEqual(stats.streaks(days, TODAY), (3, 3))
        self.assertEqual(stats.streaks([], TODAY), (0, 0))

    def test_sample_data(self):
        cal = stats.sample_calendar(TODAY)
        self.assertEqual(cal, stats.sample_calendar(TODAY))
        self.assertEqual(cal[-1][0], TODAY.isoformat())
        self.assertGreaterEqual(len(cal), 365)
        sample = stats.offline({"stars", "calendar", "languages"}, TODAY)
        self.assertEqual(sample["stars"], 0)
        self.assertTrue(sample["languages"])


class Icons(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(icons.lookup("python"), "si-python")
        self.assertEqual(icons.lookup("py"), "si-python")
        self.assertEqual(icons.lookup("nf-dev-python"), "si-python")
        self.assertEqual(icons.lookup("repo"), "oct-repo")
        self.assertIsNone(icons.lookup("not-an-icon"))

    def test_catalog(self):
        cat = icons.catalog()
        names = [i["name"] for i in cat]
        self.assertEqual(len(names), len(set(names)))
        python = next(i for i in cat if i["key"] == "si-python")
        self.assertEqual(python["name"], "python")
        self.assertIn("py", python["aliases"])
        self.assertEqual({i["group"] for i in cat}, {"GitHub", "Brands", "Linux and desktops"})

    def test_icons_in_lines(self):
        cfg = make_config(info=[":python: Lang: Python", "Time: 12:30:45", "Linux :nf-linux-archlinux:"])
        text, _, rows, _ = full(cfg)
        xml.dom.minidom.parseString(text)
        self.assertIn('<symbol id="i-si-python"', text)
        self.assertIn('href="#i-si-python"', text)
        self.assertIn("Simple Icons", text)  # the credit comment
        self.assertEqual(rows[1], ("Time", "12:30:45"))  # not an icon name: left as text
        self.assertEqual(text.count('<symbol id="i-si-python"'), 1)

    def test_unknown_nerd_font_name(self):
        with self.assertRaisesRegex(ValueError, "nf-dev-nope"):
            make_config(info=[":nf-dev-nope: hi"])


class BadgeStyles(unittest.TestCase):
    def test_every_style_and_window(self):
        pal = palette("github-dark")
        for style in badges.STYLES:
            for icon in ("", "globe", "python", "M12 2L2 22h20z"):
                with self.subTest(style=style, icon=icon):
                    (b,), _ = badges.parse([{"label": "Stars", "message": "1,234", "icon": icon, "style": style}], {})
                    xml.dom.minidom.parseString(badges.render(b, pal))
        (b,), _ = badges.parse([{"label": "A", "message": "b", "style": "window"}], {})
        for window in frames.STYLES:
            with self.subTest(window=window):
                xml.dom.minidom.parseString(badges.render(b, pal, window))

    def test_live_numbers(self):
        cfg = make_config(github="ada", badge=[{"label": "Stars", "message": "{stars} ★", "style": "social"}])
        self.assertEqual(cfg.needed_stats(), {"stars"})
        _, _, _, vals = full(cfg, {"stars": 1500})
        (b,) = config.badges_for(cfg, vals)
        self.assertEqual(b.message, "1,500 ★")
        self.assertIn("1,500", badges.render(b, palette("github-dark")))


class Endpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "readmefetch.toml"
        cls.path.write_text('user = "ada"\nhost = "engine"\nlogos = ["tux"]\n')
        cls.server = web.make_server(cls.path, port=0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        conn.request("GET", path, headers={"Host": f"127.0.0.1:{self.port}"})
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        return res.status, raw, res

    def test_state(self):
        state = json.loads(self.get("/api/state")[1])
        self.assertEqual(state["api"], web.API_VERSION)
        page = (Path(web.__file__).parent / "web" / "app.js").read_text()
        self.assertIn(f"const API_VERSION = {web.API_VERSION};", page)  # the page and server agree
        self.assertEqual(set(state["window_styles"]), set(frames.STYLES))
        self.assertIn("graph", state["visuals"])
        self.assertIn("stars", state["github_keys"])
        self.assertIn("macos", state["presets"])
        self.assertTrue(state["ui_icons"])

    def test_icons(self):
        status, raw, _ = self.get("/api/icons")
        self.assertEqual(status, 200)
        self.assertTrue(any(i["name"] == "python" for i in json.loads(raw)))

    def test_frame_and_badge(self):
        status, raw, res = self.get("/api/frame?style=win95&theme=cmd&title=MS-DOS")
        self.assertEqual(status, 200)
        self.assertEqual(res.getheader("Content-Type"), "image/svg+xml")
        xml.dom.minidom.parseString(raw)
        status, raw, _ = self.get("/api/badge?style=glass&label=Hi&message=there&icon=python")
        self.assertEqual(status, 200)
        xml.dom.minidom.parseString(raw)
        self.assertEqual(self.get("/api/badge?style=nope")[0], 404)
        self.assertEqual(self.get("/api/frame?style=nope")[0], 404)


class Commands(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_icons_and_windows(self):
        code, out = self.run_cli("icons", "python")
        self.assertEqual(code, 0)
        self.assertIn(":python: :py:", out)
        self.assertEqual(self.run_cli("icons", "zzzz-nothing")[0], 1)
        code, out = self.run_cli("windows")
        self.assertEqual(code, 0)
        for style in frames.STYLES:
            self.assertIn(style, out)

    def test_print_nerd_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "readmefetch.toml"
            path.write_text('user = "ada"\nhost = "engine"\nlogos = []\ngithub = "ada"\n'
                            'info = [":python: Stars: {stars}", "{graph}"]\n')
            code, out = self.run_cli("print", "-c", str(path), "--offline", "--color", "never", "--nerd-font")
            self.assertEqual(code, 0)
            self.assertIn(icons.glyph("si-python"), out)
            self.assertIn("Stars: 0", out)


if __name__ == "__main__":
    unittest.main()
