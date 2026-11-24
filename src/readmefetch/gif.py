"""Export the animated SVG as a GIF.

A headless Chromium-family browser (Chrome, Chromium, Brave or Edge) renders the
real SVG, so the GIF matches what GitHub shows. The browser is driven over the
DevTools protocol through a pipe (--remote-debugging-pipe), which needs only the
standard library. Every CSS animation is paused and seeked to the exact time of
each frame, so frames are deterministic and capture speed does not matter.
Pillow assembles the frames: `pip install "readmefetch[gif]"`.
"""

import base64
import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BROWSERS = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave", "brave-browser",
    "microsoft-edge", "microsoft-edge-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser() -> str:
    env = os.environ.get("READMEFETCH_BROWSER")
    if env:
        return env
    for name in BROWSERS:
        path = shutil.which(name) or (name if os.path.isabs(name) and os.path.exists(name) else None)
        if path:
            return path
    raise RuntimeError("GIF export needs Chrome, Chromium, Brave or Edge; install one or set READMEFETCH_BROWSER")


class Browser:
    """Minimal DevTools-protocol client over --remote-debugging-pipe (fd 3 in, fd 4 out)."""

    def __init__(self, executable: str):
        if os.name != "posix":
            raise RuntimeError("GIF export currently needs Linux or macOS")
        self.profile = tempfile.mkdtemp(prefix="readmefetch-browser-")
        to_child_r, self._to_child = os.pipe()
        self._from_child, from_child_w = os.pipe()
        # keep the child's ends clear of 3 and 4 so the dup2 calls below cannot clobber each other
        hi_r = fcntl.fcntl(to_child_r, fcntl.F_DUPFD, 10)
        hi_w = fcntl.fcntl(from_child_w, fcntl.F_DUPFD, 10)
        os.close(to_child_r)
        os.close(from_child_w)

        def wire():
            os.dup2(hi_r, 3)
            os.dup2(hi_w, 4)

        args = [executable, "--headless=new", "--remote-debugging-pipe", f"--user-data-dir={self.profile}",
                "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--mute-audio",
                "--disable-extensions", "--disable-gpu", "--force-color-profile=srgb"]
        if os.geteuid() == 0 or os.environ.get("CI"):
            args.append("--no-sandbox")  # CI runners and containers often cannot use Chrome's sandbox
        self.proc = subprocess.Popen(args, preexec_fn=wire, pass_fds=(3, 4), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(hi_r)
        os.close(hi_w)
        self._buf = b""
        self._next = 0

    def call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self._next += 1
        msg = {"id": self._next, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self._to_child, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self._buf:
                chunk = os.read(self._from_child, 1 << 20)
                if not chunk:
                    raise RuntimeError("the browser exited unexpectedly")
                self._buf += chunk
            raw, self._buf = self._buf.split(b"\0", 1)
            reply = json.loads(raw)
            if reply.get("id") == self._next:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error'].get('message')}")
                return reply.get("result", {})

    def close(self) -> None:
        try:
            self.call("Browser.close")
        except (RuntimeError, OSError):
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for fd in (self._to_child, self._from_child):
            try:
                os.close(fd)
            except OSError:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)  # only once the browser has fully exited


def capture(svg_path: Path, width: int, height: int, times: list[float], scale: float = 1.0) -> list:
    """PNG frames (as Pillow images) of the SVG at each time, in seconds."""
    Image = _pillow()
    browser = Browser(find_browser())
    try:
        target = browser.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = browser.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        browser.call("Emulation.setDeviceMetricsOverride",
                     {"width": width, "height": height, "deviceScaleFactor": scale, "mobile": False}, session)
        browser.call("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}}, session)
        browser.call("Page.enable", {}, session)
        browser.call("Page.navigate", {"url": svg_path.resolve().as_uri()}, session)
        wait = "new Promise(r => { const ok = () => document.readyState === 'complete' ? r(true) : setTimeout(ok, 20); ok(); })"
        browser.call("Runtime.evaluate", {"expression": wait, "awaitPromise": True}, session)
        frames = []
        for t in times:
            seek = (f"(async () => {{ for (const a of document.getAnimations()) {{ a.pause(); a.currentTime = {t * 1000:.1f}; }}"
                    " await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));"
                    " return document.getAnimations().length; })()")
            browser.call("Runtime.evaluate", {"expression": seek, "awaitPromise": True}, session)
            shot = browser.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session)
            frames.append(Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGBA"))
        return frames
    finally:
        browser.close()


def _pillow():
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError('GIF export needs Pillow: pip install "readmefetch[gif]" (or pip install pillow)') from None
    return Image


def flatness(img) -> float:
    """Standard deviation of the luminance; near 0 means a blank frame."""
    from PIL import ImageStat
    return ImageStat.Stat(img.convert("L")).stddev[0]


def write_gif(frames: list, path: Path, fps: float) -> None:
    Image = _pillow()
    # one shared palette for every frame (no colour flicker), index 255 kept for transparency
    sample = frames[:: max(1, len(frames) // 12)]
    sheet = Image.new("RGB", (sample[0].width, sample[0].height * len(sample)))
    for i, f in enumerate(sample):
        sheet.paste(f.convert("RGB"), (0, i * f.height))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    out, durations = [], []
    step = round(1000 / fps)
    for f in frames:
        p = f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        clear = f.getchannel("A").point(lambda a: 255 if a < 128 else 0)
        p.paste(255, mask=clear)
        if out and p.tobytes() == out[-1].tobytes():
            durations[-1] += step  # hold the previous frame instead of storing a duplicate
            continue
        out.append(p)
        durations.append(step)
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0,
                transparency=255, disposal=1, optimize=False)


def export(svg_text: str, meta: dict, path: Path, fps: float = 10, scale: float = 1.0, intro: bool = True,
           frames_dir: Path | None = None) -> dict:
    """Render svg_text to an animated GIF at path. Returns a small report."""
    start = 0.0 if intro else meta["intro"] + meta["period"]  # a steady-state cycle loops seamlessly
    length = (meta["intro"] + meta["period"]) if intro else meta["period"]
    count = max(1, round(length * fps))
    times = [start + i / fps for i in range(count)]
    with tempfile.TemporaryDirectory(prefix="readmefetch-") as tmp:
        svg_file = Path(tmp) / "readmefetch.svg"
        svg_file.write_text(svg_text, encoding="utf-8")
        frames = capture(svg_file, meta["width"], meta["height"], times, scale)
    last = flatness(frames[-1])
    if last < 1.0:
        print(f"readmefetch: warning: the captured frames look blank (σ={last:.2f})", file=sys.stderr)
    if frames_dir:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(frames):
            f.save(frames_dir / f"frame-{i:04d}.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_gif(frames, path, fps)
    return {"frames": len(frames), "seconds": length, "bytes": path.stat().st_size, "sigma": last}
