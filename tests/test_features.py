"""Tests for the intro, prompt and cursor settings, writing TOML, badges and the web app."""

import contextlib
import http.client
import io
import json
import re
import sys
import tempfile
import threading
import tomllib
import unittest
import xml.dom.minidom
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from test_readmefetch import make_config, render  # noqa: E402

from readmefetch import badges, cli, config, logos, svg, web  # noqa: E402
from readmefetch.themes import palette  # noqa: E402

COVER = re.compile(r'<rect class="rf-rv" x="([\d.]+)" y="([\d.]+)"[^>]*style="transform-origin:[\d.]+px [\d.]+px;'
                   r'animation:(rf-r[xy]) ([\d.]+)s steps\((\d+),end\) ([\d.]+)s both"')


def covers(text: str) -> list[dict]:
    return [{"x": float(x), "y": float(y), "axis": axis, "dur": float(dur), "steps": int(steps), "delay": float(delay)}
            for x, y, axis, dur, steps, delay in COVER.findall(text)]


class Intro(unittest.TestCase):
    def test_every_scope_and_direction(self):
        for scope in config.SCOPES:
            for direction in config.DIRECTIONS:
                with self.subTest(scope=scope, direction=direction):
                    text, meta = render(make_config(intro={"scope": scope, "direction": direction}))
                    xml.dom.minidom.parseString(text)
                    found = covers(text)
                    self.assertEqual(text.count('class="rf-rv"'), len(found))  # the pattern saw every cover
                    if scope == "none":
                        self.assertEqual(found, [])
                        continue
                    self.assertTrue(found)
                    across = direction in ("left-to-right", "right-to-left")
                    self.assertEqual({c["axis"] for c in found}, {"rf-rx" if across else "rf-ry"})
                    last = max(c["delay"] + c["dur"] for c in found)
                    self.assertLessEqual(last, meta["intro"] + 0.01)  # the intro ends after the last cover is gone

    def test_all_covers_the_logo_too(self):
        info_only = covers(render(make_config(intro={"scope": "info"}))[0])
        everything = covers(render(make_config(intro={"scope": "all"}))[0])
        info_x = min(c["x"] for c in info_only)
        self.assertGreater(info_x, svg.PAD + 10 * svg.CW)  # the info column is right of the logo
        self.assertTrue(any(c["x"] < info_x for c in everything))

    def test_speeds_follow_the_seed_and_the_variance(self):
        a = covers(render(make_config(intro={"scope": "info", "seed": 1}))[0])
        b = covers(render(make_config(intro={"scope": "info", "seed": 2}))[0])
        self.assertEqual([c["steps"] for c in a], [c["steps"] for c in b])
        self.assertNotEqual([c["dur"] for c in a], [c["dur"] for c in b])
        again = covers(render(make_config(intro={"scope": "info", "seed": 1}))[0])
        self.assertEqual(a, again)  # the same seed gives the same file
        steady = covers(render(make_config(intro={"scope": "info", "variance": 0, "speed": 40}))[0])
        for c in steady:
            self.assertAlmostEqual(c["dur"], c["steps"] / 40, delta=0.006)

    def test_reduced_motion_and_static_fallback_show_the_text(self):
        text, _ = render(make_config(intro={"scope": "all"}))
        self.assertIn(".rf-rv { opacity: 0; }", text)
        self.assertIn("prefers-reduced-motion: reduce", text)
        self.assertNotRegex(text, r'class="rf-rv"[^>]*opacity="1"')

    def test_all_skips_the_first_logo_entrance_once(self):
        text, meta = render(make_config(logos=["drone", "tux"], intro={"scope": "all"}))
        first = re.search(r"@keyframes rf-m0 \{ 0% \{ ([^}]*)\}", text).group(1)
        self.assertIn("translateY(0)", first)  # typed in place, so it starts at rest instead of flying in
        delay = float(re.search(r"\.rf-m0 \{ animation: rf-m0 [\d.]+s ([\d.]+)s infinite", text).group(1))
        self.assertAlmostEqual(delay, meta["intro"], delta=0.01)
        plain, _ = render(make_config(logos=["drone", "tux"], intro={"scope": "info"}))
        self.assertRegex(plain, r"@keyframes rf-m0 \{ 0% \{ transform: translateY\(-")  # flies in as usual

    def test_rotate(self):
        frames = [(0, "a", "step-end"), (30, "b", "step-end"), (100, "b")]
        out = svg.rotate(frames, 10)
        self.assertEqual(out[0][:2], (0, "a"))
        self.assertEqual([f[1] for f in out if abs(f[0] - 20) < 1e-9], ["b"])
        self.assertEqual(out[-1][:2], (100, "a"))
        self.assertEqual([f[0] for f in out], sorted(f[0] for f in out))
        self.assertEqual(svg.rotate(frames, 30 + 1e-9)[0][:2], (0, "b"))  # lands on the keyframe
        self.assertIs(svg.rotate(frames, 0), frames)
        with self.assertRaises(ValueError):
            svg.rotate([(0, "a", "linear"), (50, "b"), (100, "a")], 25)  # would cut a moving segment


class PromptAndCursor(unittest.TestCase):
    def test_prompt_cwd_and_window(self):
        text, _ = render(make_config(cwd="~/code", prompt={"format": "[{user}@{host} {cwd}]$ "},
                                     window={"title": "{cwd} on {host}", "buttons": False}))
        self.assertIn(">~/code on engine</text>", text)
        self.assertIn("~/code", re.sub(r"<title.*?</title>", "", text))
        self.assertNotIn("#ff5f57", text)
        with_buttons, _ = render(make_config())
        self.assertIn("#ff5f57", with_buttons)

    def test_cursor_styles(self):
        def cursor(text):
            return re.search(r'<rect class="rf-cursor" [^>]*>', text).group(0)
        self.assertIn('width="2"', cursor(render(make_config(cursor={"style": "bar"}))[0]))
        under, _ = render(make_config(cursor={"style": "underline", "blink": False}))
        self.assertIn('height="2"', cursor(under))
        self.assertNotIn("rf-blink", under)
        self.assertIn("rf-blink", render(make_config())[0])

    def test_default_command(self):
        self.assertEqual(config.Config().command, "readmefetch")
        self.assertIn(": readmefetch</title>", render(make_config())[0])

    def test_bad_settings_are_reported(self):
        for bad in ({"intro": {"scope": "most"}}, {"intro": {"direction": "diagonal"}}, {"intro": {"speed": 0}},
                    {"cursor": {"style": "beam"}}, {"prompt": {"format": "{nope}$ "}}, {"prompt": {"user_color": "nope"}},
                    {"intro": {"sped": 3}}, {"window": {"buttons": "yes"}}, {"intro": "fast"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                make_config(**bad)


class Writing(unittest.TestCase):
    def test_dump_round_trips_everything(self):
        art = "\n $1/\\\n$2'''x'''\n"  # a leading blank row, a backslash and triple quotes
        cfg = make_config(
            cwd="~/x", intro={"scope": "all", "direction": "bottom-to-top", "speed": 30}, cursor={"style": "bar"},
            logos=["tux", "mine"],
            logo={"tux": {"enter": "fade"},
                  "mine": {"colors": ["red", "#00ff00"], "art": art, "credit": "me",
                           "layers": [{"row": 1, "col": 0, "period": 0.5, "weights": [1, 2], "frames": ["$1a", "$2b"]}]}},
            badges={"style": "pill"}, badge=[{"label": "Site", "message": "a.b", "link": "https://a.b", "icon": "globe"}])
        data = config.to_dict(cfg)
        text = config.dump(data)
        again = config.from_dict(tomllib.loads(text))
        self.assertEqual(config.to_dict(again), data)
        self.assertEqual(again.load_logos()[1].art, cfg.load_logos()[1].art)
        self.assertEqual(again.load_logos()[0].enter, "fade")

    def test_template_and_dump_of_defaults_load(self):
        self.assertIsInstance(config.from_dict(tomllib.loads(config.dump(config.to_dict(config.Config())))), config.Config)

    def test_builtin_overrides(self):
        tux = logos.load("tux", {"customs": {"tux": {"animate": False, "enter": "fly", "hover": True}}})
        self.assertEqual((tux.enter, tux.hover, tux.layers), ("fly", True, []))
        self.assertEqual(tux.credit, logos.load("tux").credit)
        with self.assertRaises(ValueError):
            logos.load("tux", {"customs": {"tux": {"credit": "mine now"}}})

    def test_to_dollar_round_trip(self):
        still = logos.load("drone", {"initials": "AO"}).still()
        text, colors = logos.to_dollar(still)
        self.assertEqual(logos._trim(logos.parse_dollar(text, colors)), logos._trim([list(r) for r in still]))


class Badges(unittest.TestCase):
    pal = palette("github-dark")

    def test_every_style_is_well_formed(self):
        for style in badges.STYLES:
            for icon in ["", "globe", "M12 2L2 22h20z"]:
                with self.subTest(style=style, icon=icon):
                    text = badges.render(badges.Badge("Site", "example.com & co", color="#00d4ff", icon=icon, style=style),
                                         self.pal)
                    dom = xml.dom.minidom.parseString(text)
                    self.assertGreater(float(dom.documentElement.getAttribute("width")), 40)
                    self.assertIn("Site: example.com &amp; co", text)
                    self.assertNotIn("<script", text)

    def test_width_grows_with_the_text(self):
        def width(message):
            text = badges.render(badges.Badge("Site", message, style="flat"), self.pal)
            return float(xml.dom.minidom.parseString(text).documentElement.getAttribute("width"))
        self.assertLess(width("a.b"), width("a-much-longer-domain.example"))

    def test_text_contrast(self):
        light = badges.render(badges.Badge("", "x", color="#00d4ff", style="flat-square"), self.pal)
        dark = badges.render(badges.Badge("", "x", color="#0a66c2", style="flat-square"), self.pal)
        self.assertIn('fill="#1f2328">x</text>', light)
        self.assertIn('fill="#ffffff">x</text>', dark)

    def test_terminal_cursor(self):
        on = badges.render(badges.Badge("Site", "a.b", style="terminal"), self.pal)
        off = badges.render(badges.Badge("Site", "a.b", style="terminal", cursor=False), self.pal)
        self.assertIn("@keyframes", on)
        self.assertIn("prefers-reduced-motion", on)
        self.assertNotIn("@keyframes", off)

    def test_parse_defaults_and_errors(self):
        items, d = badges.parse([{"label": "A b!"}], {"style": "pill"})
        self.assertEqual((items[0].file, items[0].style, d["dir"]), ("a-b.svg", "pill", "badges"))
        for bad in ([{"label": "a"}, {"label": "a"}], [{"label": "a", "style": "3d"}], [{"label": "a", "icon": "<script>"}],
                    [{"message": ""}], [{"label": "a", "file": "../x.svg"}], [{"label": "a", "colour": "red"}], {"label": "a"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                badges.parse(bad, {})
        for folder in ("/tmp/x", "../x", "a/../../x", "C:/x", ""):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                badges.parse([], {"dir": folder})
        with self.assertRaises(ValueError):
            make_config(badge=[{"label": "a", "color": "not-a-colour"}])

    def test_snippet(self):
        items, _ = badges.parse([{"label": "Site", "message": "a.b", "link": "https://a.b"}, {"label": "Plain"}], {})
        md = badges.snippet(items, "assets/badges")
        self.assertIn("[![Site: a.b](assets/badges/site.svg)](https://a.b)", md)
        self.assertIn("![Plain](assets/badges/plain.svg)", md)
        html = badges.snippet(items, "assets/badges", html=True)
        self.assertIn('<a href="https://a.b"><img src="assets/badges/site.svg"', html)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_render_and_badges_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "readmefetch.toml"
            path.write_text('user = "a"\nhost = "b"\n[badges]\ndir = "b"\n[[badge]]\nlabel = "Hi"\nmessage = "there"\n')
            code, out, _ = self.run_cli("render", "-c", str(path), "--offline")
            self.assertEqual(code, 0)
            written = out.split()
            self.assertEqual([Path(p).name for p in written], ["readmefetch.svg", "hi.svg"])
            self.assertTrue(all(Path(p).is_file() for p in written))
            code, out, _ = self.run_cli("badges", "-c", str(path))
            self.assertEqual((code, out), (0, "![Hi: there](b/hi.svg)\n"))
            path.write_text('user = "a"\nhost = "b"\n')
            self.assertEqual(self.run_cli("badges", "-c", str(path))[0], 1)


class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "readmefetch.toml"
        cls.path.write_text('user = "ada"\nhost = "engine"\nlogos = ["tux"]\n# a comment\n')
        cls.server = web.make_server(cls.path, port=0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def call(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        hdrs = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        conn.request("POST" if body is not None else "GET", path, body=data, headers=hdrs)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        try:
            return res.status, json.loads(raw), res
        except ValueError:
            return res.status, raw, res

    def state(self):
        return self.call("/api/state")[1]

    def test_page_and_state(self):
        status, page, res = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn(b"/app.js", page)
        self.assertIn("script-src 'self'", res.getheader("Content-Security-Policy"))
        self.assertEqual(self.call("/app.js")[0], 200)
        state = self.state()
        self.assertEqual(state["config"]["user"], "ada")
        self.assertIn("terminal", state["badge_styles"])
        self.assertIn("globe", state["icons"])

    def test_render_and_errors(self):
        cfg = self.state()["config"]
        status, out, _ = self.call("/api/render", {"config": dict(cfg, badge=[{"label": "Hi", "link": "https://a.b"}])})
        self.assertTrue(out["ok"], out)
        xml.dom.minidom.parseString(out["svg"])
        self.assertEqual(out["badges"][0]["file"], "hi.svg")
        self.assertIn("[![Hi](badges/hi.svg)](https://a.b)", out["badge_snippet"])
        status, out, _ = self.call("/api/render", {"config": dict(cfg, theme="nope")})
        self.assertEqual(status, 200)
        self.assertFalse(out["ok"])
        self.assertIn("unknown theme", out["error"])

    def test_guards(self):
        before = self.path.read_bytes()
        self.assertEqual(self.call("/api/state", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.call("/api/save", {"config": {}}, headers={"Host": f"evil.example:{self.port}"})[0], 403)
        self.assertEqual(self.call("/api/save", {"config": {}}, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.call("/api/save", b"a=1", headers={"Content-Type": "application/x-www-form-urlencoded"})[0], 415)
        self.assertEqual(self.call("/api/save", b"{oops")[0], 400)
        self.assertEqual(self.call("/nope")[0], 404)
        self.assertEqual(self.path.read_bytes(), before)  # nothing was written

    def test_save_backs_up_and_writes(self):
        original = self.path.read_text()
        try:
            cfg = dict(self.state()["config"], badge=[{"label": "Hi"}])
            status, out, _ = self.call("/api/save", {"config": cfg})
            self.assertTrue(out["ok"], out)
            self.assertEqual(Path(out["backup"]).read_text(), original)
            self.assertTrue((self.path.parent / "readmefetch.svg").is_file())
            self.assertTrue((self.path.parent / "badges" / "hi.svg").is_file())
            self.assertEqual(out["badges"], 1)
            saved = config.load(self.path)
            self.assertEqual((saved.user, [b.label for b in saved.badges]), ("ada", ["Hi"]))
        finally:
            self.path.write_text(original)

    def test_logos(self):
        status, out, _ = self.call("/api/logo", {"spec": {"art": "$1/\\", "colors": ["red"]}, "name": "x"})
        self.assertTrue(out["ok"], out)
        xml.dom.minidom.parseString(out["svg"])
        status, out, _ = self.call("/api/builtin", {"name": "tux"})
        self.assertTrue(out["ok"] and out["art"] and out["credit"], out)
        status, body, res = self.call("/api/thumb?name=tux&theme=github-dark")
        self.assertEqual((status, res.getheader("Content-Type")), (200, "image/svg+xml"))
        self.assertEqual(self.call("/api/thumb?name=no-such-logo")[0], 404)


if __name__ == "__main__":
    unittest.main()
