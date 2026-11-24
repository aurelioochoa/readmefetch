"""`readmefetch web`: a small local web app for building a readmefetch.toml with a live preview.

Standard library only. The page (web/index.html, app.css, app.js) edits the config as
JSON and asks this server to render it, so the preview, the SVG you download and the
GIF all come from the same renderer as the command line.

It listens on 127.0.0.1 only, answers only requests addressed to that host (so other
web pages can't reach it through DNS rebinding), takes only same-origin JSON posts, and
writes nothing to disk until you press Save.
"""

import datetime as dt
import json
import shutil
import sys
import tempfile
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import HOMEPAGE, __version__, badges, config, figlet, logos, stats, svg
from .themes import THEMES, palette

STATIC = Path(__file__).parent / "web"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
MAX_BODY = 4 * 1024 * 1024
STATS_TTL = 600  # seconds to reuse live GitHub numbers, so typing doesn't hit the API on every key


def gif_status() -> dict:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return {"available": False, "reason": 'GIF export needs Pillow: pip install "readmefetch[gif]"'}
    try:
        from .gif import find_browser
        return {"available": True, "browser": find_browser()}
    except (ImportError, RuntimeError) as e:
        return {"available": False, "reason": str(e)}


class App:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self._stats: dict = {}
        self._gif_lock = threading.Lock()
        self._catalog: list | None = None

    # -- the config ---------------------------------------------------------------------

    def starter(self) -> dict:
        text = config.TEMPLATE.format(
            user="you", host="github", lang="python", since=dt.date.today().replace(month=1, day=1).isoformat(),
            bio="Software Developer", location="Earth", blog="you@example.com",
            github_line='# github = "your-username"', github_info="")
        import tomllib
        return config.to_dict(config.from_dict(tomllib.loads(text)))

    def state(self) -> dict:
        error = ""
        data = None
        if self.path.exists():
            try:
                data = config.to_dict(config.load(self.path))
            except (ValueError, OSError) as e:
                error = f"{self.path.name} has a problem, so this starts from the example instead: {e}"
        return {
            "config": data or self.starter(),
            "exists": self.path.exists(),
            "path": str(self.path),
            "error": error,
            "version": __version__,
            "homepage": HOMEPAGE,
            "themes": THEMES,
            "logos": self.catalog(),
            "fonts": figlet.fonts(),
            "placeholders": config.PLACEHOLDERS,
            "scopes": config.SCOPES,
            "directions": config.DIRECTIONS,
            "cursors": list(config.CURSORS),
            "enters": list(logos.ENTERS),
            "badge_styles": badges.STYLES,
            "icons": badges.ICONS,
            "defaults": {name: config.to_dict(config.Config())[name] for name in config.TABLES},
            "gif": gif_status(),
        }

    def catalog(self) -> list:
        if self._catalog is None:
            groups = {"readmefetch": "Animated", "candybox2": "Animated", "fastfetch": "Operating systems",
                      "onefetch": "Languages"}
            out = []
            for name, source in logos.catalog():
                lg = logos.load(name, {"initials": "RF", "user": "readmefetch"})
                group = "Animated" if lg.layers or name == "banner" else groups.get(lg.source, "Other")
                out.append({"name": name, "source": source, "credit": lg.credit, "group": group,
                            "enter": lg.enter, "hover": lg.hover, "accent": lg.accent, "animated": bool(lg.layers)})
            self._catalog = out
        return self._catalog

    def numbers(self, cfg: config.Config, live: bool) -> tuple[dict, str]:
        needed = cfg.needed_stats()
        if not needed:
            return {}, ""
        if not live:
            return stats.offline(needed), "Live numbers are off: they show as 0."
        key = (cfg.github.lower(), frozenset(needed))
        hit = self._stats.get(key)
        if hit and time.time() - hit[0] < STATS_TTL:
            return hit[1], hit[2]
        try:
            got = stats.fetch(cfg.github, needed)
            note = ("" if got.get("contributions") != "?"
                    else "{contributions} needs a GitHub token (GITHUB_TOKEN, GH_TOKEN or gh auth login).")
        except (OSError, RuntimeError, KeyError) as e:
            got, note = stats.offline(needed), f"Couldn't reach the GitHub API ({e}); numbers show as 0."
        self._stats[key] = (time.time(), got, note)
        return got, note

    def render(self, data: dict, live: bool) -> dict:
        cfg = config.from_dict(data, self.path)
        numbers, note = self.numbers(cfg, live)
        rows = config.info_rows(cfg, config.values(cfg, numbers, dt.date.today()))
        text, meta = svg.render(cfg, rows, cfg.load_logos(), palette(cfg.theme, cfg.colors))
        pal = palette(cfg.theme, cfg.colors)
        badge_svgs = [{"file": b.file, "svg": badges.render(b, pal), "text": b.text, "link": b.link} for b in cfg.badges]
        alt = f"A terminal runs {cfg.command or 'a command'} for {cfg.title}"
        details = "; ".join(f"{r[0]}: {r[1]}" if r[0] else r[1] for r in rows if r)
        return {"svg": text, **meta, "note": note, "toml": config.dump(data), "output": cfg.output,
                "alt": f"{alt}: {details}" if details else alt, "cfg": cfg, "badges": badge_svgs,
                "badge_snippet": badges.snippet(cfg.badges, cfg.badge_defaults["dir"])}

    def save(self, data: dict, live: bool) -> dict:
        result = self.render(data, live)
        cfg = result["cfg"]
        backup = ""
        if self.path.exists() and self.path.read_text(encoding="utf-8") != result["toml"]:
            bak = self.path.with_name(self.path.name + ".bak")
            shutil.copy2(self.path, bak)
            backup = str(bak)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(result["toml"], encoding="utf-8")
        out = (self.path.parent / cfg.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result["svg"], encoding="utf-8")
        badge_dir = self.path.parent / cfg.badge_defaults["dir"]
        if result["badges"]:
            badge_dir.mkdir(parents=True, exist_ok=True)
        for b in result["badges"]:
            (badge_dir / b["file"]).write_text(b["svg"], encoding="utf-8")
        return {"config_path": str(self.path), "svg_path": str(out), "backup": backup,
                "badges": len(result["badges"]), "badge_dir": str(badge_dir.resolve())}

    def gif(self, data: dict, live: bool, fps: float, scale: float, intro: bool) -> bytes:
        from . import gif
        if not self._gif_lock.acquire(blocking=False):
            raise RuntimeError("a GIF is already being made; wait for it to finish")
        try:
            result = self.render(data, live)
            meta = {k: result[k] for k in ("width", "height", "intro", "period")}
            with tempfile.TemporaryDirectory(prefix="readmefetch-web-") as tmp:
                path = Path(tmp) / "readmefetch.gif"
                gif.export(result["svg"], meta, path, fps=fps, scale=scale, intro=intro)
                return path.read_bytes()
        finally:
            self._gif_lock.release()

    def logo(self, body: dict) -> dict:
        spec = body.get("spec") or {}
        pal = palette(str(body.get("theme", "github-dark")), body.get("colors") or {})
        name = str(body.get("name") or "preview")
        if "art" in spec:
            lg = logos.custom(name, spec)
        else:
            lg = logos.load(name, {"initials": body.get("initials") or "RF", "user": body.get("user") or "you",
                                   "banner": body.get("banner") or {}, "customs": {name: spec} if spec else {}})
        text, meta = svg.render_logo(lg, pal)
        return {"svg": text, **meta}

    def builtin(self, name: str, ctx: dict) -> dict:
        lg = logos.load(name, {"initials": ctx.get("initials") or "RF", "user": ctx.get("user") or "you",
                               "banner": ctx.get("banner") or {}})
        art, colors = logos.to_dollar(lg.still())
        return {"name": lg.name, "art": art, "colors": colors or ["fg"], "credit": lg.credit, "accent": lg.accent}


class Handler(BaseHTTPRequestHandler):
    server_version = f"readmefetch/{__version__}"
    app: App
    allowed_hosts: set[str] = set()
    quiet = True

    def log_message(self, fmt, *args):
        if not self.quiet:
            super().log_message(fmt, *args)

    # -- plumbing -----------------------------------------------------------------------

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.allowed_hosts

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj, default=str).encode(), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"ok": False, "error": message}, status)

    # -- GET ----------------------------------------------------------------------------

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._static("index.html")
        if url.path in ("/app.js", "/app.css", "/favicon.svg"):
            return self._static(url.path[1:])
        if url.path == "/api/state":
            return self._json(self.app.state())
        if url.path == "/api/thumb":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                body = {"name": q.get("name", ""), "theme": q.get("theme", "github-dark"),
                        "user": q.get("user", ""), "initials": q.get("initials", "")}
                text = self.app.logo(body)["svg"]
            except (ValueError, KeyError) as e:
                return self._error(HTTPStatus.NOT_FOUND, str(e))
            return self._send(200, text.encode(), "image/svg+xml", {"Cache-Control": "max-age=300"})
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def _static(self, name: str) -> None:
        path = STATIC / name
        if not path.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        csp = ("default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; "
               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self._send(200, path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"),
                   {"Content-Security-Policy": csp} if name.endswith(".html") else None)

    # -- POST ---------------------------------------------------------------------------

    def do_POST(self):  # noqa: N802
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        origin = self.headers.get("Origin")
        if origin and origin.removeprefix("http://") not in self.allowed_hosts:
            return self._error(HTTPStatus.FORBIDDEN, "cross-origin requests are not allowed")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "send JSON")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request too large")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._error(HTTPStatus.BAD_REQUEST, "invalid JSON")
        route = urlparse(self.path).path
        live = bool(body.get("live"))
        try:
            if route == "/api/render":
                result = self.app.render(body.get("config") or {}, live)
                result.pop("cfg")
                return self._json({"ok": True, **result})
            if route == "/api/save":
                return self._json({"ok": True, **self.app.save(body.get("config") or {}, live)})
            if route == "/api/logo":
                return self._json({"ok": True, **self.app.logo(body)})
            if route == "/api/builtin":
                return self._json({"ok": True, **self.app.builtin(str(body.get("name", "")), body)})
            if route == "/api/gif":
                fps = min(max(float(body.get("fps", 10)), 1), 30)
                scale = min(max(float(body.get("scale", 1)), 0.5), 3)
                data = self.app.gif(body.get("config") or {}, live, fps, scale, bool(body.get("intro", True)))
                return self._send(200, data, "image/gif")
        except (ValueError, TypeError, KeyError) as e:
            return self._json({"ok": False, "error": str(e)})
        except (RuntimeError, OSError) as e:
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
        self._error(HTTPStatus.NOT_FOUND, "not found")


def make_server(path: Path, port: int = 8765, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": App(path)})
    server = ThreadingHTTPServer((host, port), handler)
    real_port = server.server_address[1]
    handler.allowed_hosts = {f"127.0.0.1:{real_port}", f"localhost:{real_port}", f"[::1]:{real_port}"}
    return server


def serve(path: Path, port: int = 8765, open_browser: bool = False, verbose: bool = False) -> int:
    try:
        server = make_server(path, port)
    except OSError as e:
        raise RuntimeError(f"can't listen on port {port} ({e.strerror}); try --port {port + 1}") from None
    server.RequestHandlerClass.quiet = not verbose
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"readmefetch web: {url}  (editing {path}; Ctrl-C to stop)", file=sys.stderr)
    if open_browser:
        threading.Timer(0.3, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nreadmefetch web: stopped", file=sys.stderr)
    finally:
        server.server_close()
    return 0
