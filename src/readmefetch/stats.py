"""Live numbers from the GitHub API for the info lines and badges.

Plain numbers: {repos} {stars} {forks} {followers} {following} {gists} {joined}
need no token (the REST API answers anonymously, 60 requests an hour).
{contributions} {commits} {prs} {issues} {reviews} {streak} {longest_streak} and the
contribution calendar behind {graph} and {heatmap} need a token (GraphQL): the Action
passes one, and locally GITHUB_TOKEN, GH_TOKEN or `gh auth login` work.
Languages ({top_language} {languages} {langbar}) are measured in bytes with a token,
and estimated from each repository's main language and size without one.
"""

import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://api.github.com"

USER_KEYS = {"repos", "followers", "following", "gists", "joined"}
REPO_KEYS = {"stars", "forks"}
CALENDAR_KEYS = {"contributions", "commits", "reviews", "streak", "longest_streak", "calendar"}
TOTAL_KEYS = {"prs", "issues"}
LANGUAGE_KEYS = {"languages"}
TOKEN_KEYS = CALENDAR_KEYS  # can't be had without a token

# Linguist colours (MIT, github-linguist) for the estimate made without a token.
LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Go": "#00ADD8", "Rust": "#dea584",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Java": "#b07219", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "Dart": "#00B4AB", "Ruby": "#701516", "PHP": "#4F5D95", "Lua": "#000080", "Shell": "#89e051",
    "PowerShell": "#012456", "HTML": "#e34c26", "CSS": "#663399", "SCSS": "#c6538c", "Sass": "#a53b70",
    "Vue": "#41b883", "Svelte": "#ff3e00", "Astro": "#ff5a03", "Jupyter Notebook": "#DA5B0B", "R": "#198CE7",
    "Julia": "#a270ba", "Haskell": "#5e5086", "Elixir": "#6e4a7e", "Erlang": "#B83998", "Scala": "#c22d40",
    "Clojure": "#db5855", "Zig": "#ec915c", "Nim": "#ffc200", "OCaml": "#ef7a08", "F#": "#b845fc", "Perl": "#0298c3",
    "Dockerfile": "#384d54", "Makefile": "#427819", "Nix": "#7e7eff", "Vim Script": "#199f4b", "Emacs Lisp": "#c065db",
    "TeX": "#3D6117", "Objective-C": "#438eff", "GDScript": "#355570", "Assembly": "#6E4C13", "Groovy": "#4298b8",
    "Blade": "#f7523f", "Hack": "#878787", "MDX": "#fcb32c", "Markdown": "#083fa1", "Solidity": "#AA6746",
}
OTHER_COLOR = "#8b949e"


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


def _graphql(query: str, variables: dict, tok: str) -> dict:
    d = _call(f"{API}/graphql", tok, {"query": query, "variables": variables})
    if d.get("errors"):
        raise RuntimeError(d["errors"][0].get("message", "GraphQL error"))
    return d["data"]


CALENDAR_QUERY = """query($login: String!) { user(login: $login) {
  contributionsCollection {
    totalCommitContributions totalPullRequestReviewContributions restrictedContributionsCount
    contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel } } }
  }
  pullRequests { totalCount } issues { totalCount }
} }"""

LANGUAGES_QUERY = """query($login: String!, $after: String) { user(login: $login) {
  repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
    pageInfo { hasNextPage endCursor }
    nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
  }
} }"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def streaks(days: list[tuple[str, int, int]], today: dt.date | None = None) -> tuple[int, int]:
    """(current, longest) runs of days with a contribution. Today not counted yet doesn't break the streak."""
    longest = run = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    rest = list(days)
    if rest and not rest[-1][1] and rest[-1][0] == (today or dt.date.today()).isoformat():
        rest = rest[:-1]  # nothing yet today: the streak still counts up to yesterday
    for _, count, _ in reversed(rest):
        if not count:
            break
        current += 1
    return current, longest


def _repos(user: str, tok: str) -> list[dict]:
    out, page = [], 1
    while page <= 10:
        repos = _call(f"{API}/users/{user}/repos?per_page=100&type=owner&page={page}", tok)
        out += [r for r in repos if not r.get("fork")]
        if len(repos) < 100:
            break
        page += 1
    return out


def fetch(user: str, needed: set[str]) -> dict:
    """The raw numbers (and lists) behind the placeholders in `needed`."""
    tok = token()
    out: dict = {}
    if needed & USER_KEYS:
        u = _call(f"{API}/users/{user}", tok)
        out.update(repos=u["public_repos"], followers=u["followers"], following=u["following"],
                   gists=u["public_gists"], joined=(u.get("created_at") or "")[:4])
    repos = None
    if needed & REPO_KEYS or (needed & LANGUAGE_KEYS and not tok):
        repos = _repos(user, tok)
        out["stars"] = sum(r["stargazers_count"] for r in repos)
        out["forks"] = sum(r["forks_count"] for r in repos)
    if needed & (CALENDAR_KEYS | TOTAL_KEYS):
        if not tok:
            missing = sorted(needed & (CALENDAR_KEYS | TOTAL_KEYS))
            print(f"readmefetch: {', '.join('{' + k + '}' for k in missing)} need a token (GITHUB_TOKEN, GH_TOKEN or "
                  "`gh auth login`); showing '?'", file=sys.stderr)
            out.update({k: "?" for k in CALENDAR_KEYS | TOTAL_KEYS})
            out["calendar"] = []
            if needed & TOTAL_KEYS:  # the search API answers without a token
                for key, kind in (("prs", "pr"), ("issues", "issue")):
                    q = urllib.parse.quote(f"author:{user} type:{kind}")
                    out[key] = _call(f"{API}/search/issues?q={q}&per_page=1", tok)["total_count"]
        else:
            u = _graphql(CALENDAR_QUERY, {"login": user}, tok)["user"]
            cc = u["contributionsCollection"]
            cal = cc["contributionCalendar"]
            days = [(d["date"], d["contributionCount"], LEVELS.get(d["contributionLevel"], 0))
                    for w in cal["weeks"] for d in w["contributionDays"]]
            current, longest = streaks(days)
            out.update(contributions=cal["totalContributions"], commits=cc["totalCommitContributions"],
                       reviews=cc["totalPullRequestReviewContributions"], prs=u["pullRequests"]["totalCount"],
                       issues=u["issues"]["totalCount"], streak=current, longest_streak=longest, calendar=days)
    if needed & LANGUAGE_KEYS:
        sizes: dict[str, list] = {}
        if tok:
            after = None
            for _ in range(5):
                r = _graphql(LANGUAGES_QUERY, {"login": user, "after": after}, tok)["user"]["repositories"]
                for node in r["nodes"]:
                    for e in node["languages"]["edges"]:
                        entry = sizes.setdefault(e["node"]["name"], [0, e["node"]["color"] or OTHER_COLOR])
                        entry[0] += e["size"]
                if not r["pageInfo"]["hasNextPage"]:
                    break
                after = r["pageInfo"]["endCursor"]
        else:
            for r in repos or []:
                if r.get("language"):
                    entry = sizes.setdefault(r["language"], [0, LANGUAGE_COLORS.get(r["language"], OTHER_COLOR)])
                    entry[0] += max(r.get("size") or 0, 1)
        out["languages"] = sorted(((name, size, color) for name, (size, color) in sizes.items()), key=lambda x: -x[1])
    return out


def offline(needed: set[str], today: dt.date | None = None) -> dict:
    """Stand-ins when the API is off: 0 for numbers, and made-up sample data for the graphs, so a preview
    still shows what they look like."""
    out: dict = {k: 0 for k in needed}
    if "joined" in needed:
        out["joined"] = "2020"
    if needed & CALENDAR_KEYS:
        out["calendar"] = sample_calendar(today or dt.date.today())
    if needed & LANGUAGE_KEYS:
        out["languages"] = [("Python", 46, "#3572A5"), ("TypeScript", 27, "#3178c6"), ("Go", 12, "#00ADD8"),
                            ("Shell", 8, "#89e051"), ("Lua", 4, "#000080"), ("CSS", 3, "#663399")]
    return out


def sample_calendar(today: dt.date) -> list[tuple[str, int, int]]:
    """A year of plausible, repeatable contribution days ending today."""
    rng = random.Random(7)
    start = today - dt.timedelta(days=364 + (today.weekday() + 1) % 7)
    days = []
    d = start
    while d <= today:
        busy = 0.55 + 0.35 * ((d - start).days % 70 > 35)
        count = 0 if rng.random() > busy or d.weekday() == 6 else int(rng.expovariate(1 / 4)) + 1
        days.append((d.isoformat(), count, 0))
        d += dt.timedelta(days=1)
    return with_levels(days)


def with_levels(days: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Fill in GitHub-like levels 1-4 (quartiles of the non-zero days)."""
    counts = sorted(c for _, c, _ in days if c)
    if not counts:
        return [(d, c, 0) for d, c, _ in days]
    cuts = [counts[min(len(counts) - 1, int(len(counts) * q))] for q in (0.25, 0.5, 0.75)]
    return [(d, c, 0 if not c else 1 + sum(c > cut for cut in cuts)) for d, c, _ in days]


def profile(user: str) -> dict:
    """Public profile fields used by `readmefetch init --github`."""
    return _call(f"{API}/users/{user}", token())
