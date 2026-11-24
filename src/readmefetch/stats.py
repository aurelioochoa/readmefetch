"""Live numbers from the GitHub API for {repos}, {stars}, {followers}, {contributions}."""

import json
import os
import shutil
import subprocess
import sys
import urllib.request

API = "https://api.github.com"


def token() -> str:
    """GITHUB_TOKEN / GH_TOKEN, else the GitHub CLI's login if it is installed."""
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    if shutil.which("gh"):
        try:
            out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
            if out.returncode == 0:
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def _call(url: str, tok: str, body: dict | None = None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "readmefetch"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch(user: str, needed: set[str]) -> dict:
    tok = token()
    out: dict = {}
    if needed & {"repos", "followers"}:
        u = _call(f"{API}/users/{user}", tok)
        out["repos"], out["followers"] = u["public_repos"], u["followers"]
    if "stars" in needed:
        stars, page = 0, 1
        while True:
            repos = _call(f"{API}/users/{user}/repos?per_page=100&type=owner&page={page}", tok)
            stars += sum(r["stargazers_count"] for r in repos if not r.get("fork"))
            if len(repos) < 100:
                break
            page += 1
        out["stars"] = stars
    if "contributions" in needed:
        if not tok:
            print("readmefetch: {contributions} needs a token (GITHUB_TOKEN, GH_TOKEN or `gh auth login`); showing '?'",
                  file=sys.stderr)
            out["contributions"] = "?"
        else:
            q = ("query($login: String!) { user(login: $login) "
                 "{ contributionsCollection { contributionCalendar { totalContributions } } } }")
            d = _call(f"{API}/graphql", tok, {"query": q, "variables": {"login": user}})
            if d.get("errors"):
                raise RuntimeError(d["errors"][0].get("message", "GraphQL error"))
            out["contributions"] = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return out


def offline(needed: set[str]) -> dict:
    return {k: 0 for k in needed}


def profile(user: str) -> dict:
    """Public profile fields used by `readmefetch init --github`."""
    return _call(f"{API}/users/{user}", token())

