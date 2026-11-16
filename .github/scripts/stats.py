#!/usr/bin/env python3
"""Generate assets/stats.svg from the GitHub GraphQL API.

Dijalankan oleh .github/workflows/stats.yml (butuh env GITHUB_TOKEN).
Tanpa dependency eksternal: hanya stdlib.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.request

LOGIN = os.environ.get("PROFILE_LOGIN", "muhamadjordysetiawan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"

# Palet arcade: kuning Pac-Man, cyan, pink, coral, lime
PALETTE = ["#22D3EE", "#FACC15", "#F472B6", "#FB923C", "#A3E635", "#8B5CF6"]
BG = "#0B1220"
GRID = "#1B2740"
TEXT = "#E6EDF3"
MUTED = "#8B98AC"
ACCENT = "#FACC15"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        f"{API}/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-generator",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def streaks(days: list[dict]) -> tuple[int, int]:
    """Kembalikan (streak saat ini, streak terpanjang) dalam hari."""
    if not days:
        return 0, 0

    parsed = sorted(
        (dt.date.fromisoformat(d["date"]), int(d["contributionCount"])) for d in days
    )

    longest = current = 0
    previous = None
    for day, count in parsed:
        if count > 0:
            current = current + 1 if previous == day - dt.timedelta(days=1) else 1
            longest = max(longest, current)
        else:
            current = 0
        previous = day

    # Hari ini mungkin belum ada kontribusi: streak tetap dihitung dari kemarin.
    today = dt.date.today()
    tail = 0
    for day, count in reversed(parsed):
        if day > today:
            continue
        if count > 0:
            tail += 1
        elif day == today:
            continue
        else:
            break
    return tail, longest


LABEL_OVERRIDES = {"PLpgSQL": "PostgreSQL", "TSQL": "SQL", "Hack": "Hack/PHP"}


def language_totals(repos: list[dict]) -> tuple[list[tuple[str, int]], int]:
    totals: dict[str, int] = {}
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name = LABEL_OVERRIDES.get(edge["node"]["name"], edge["node"]["name"])
            totals[name] = totals.get(name, 0) + edge["size"]
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:5]
    return ranked, sum(totals.values())


def fmt(number: int) -> str:
    if number >= 1000:
        return f"{number / 1000:.1f}k".replace(".0k", "k")
    return str(number)


def pacman(cx: float, cy: float, size: float, color: str = ACCENT) -> str:
    r = size / 2
    lips_x = cx + r * 0.819
    lips_y = r * 0.574
    return (
        f'<path d="M{cx} {cy}L{lips_x:.2f} {cy - lips_y:.2f}'
        f'A{r:.2f} {r:.2f} 0 1 0 {lips_x:.2f} {cy + lips_y:.2f}Z" fill="{color}"/>'
    )


def build_svg(data: dict) -> str:
    user = data["user"]
    repos = user["repositories"]["nodes"]
    repo_count = user["repositories"]["totalCount"]
    stars = sum(int(repo.get("stargazerCount", 0)) for repo in repos)
    followers = user["followers"]["totalCount"]
    collection = user["contributionsCollection"]
    contributions = collection["contributionCalendar"]["totalContributions"]
    commits = collection["totalCommitContributions"]

    days = [
        day
        for week in collection["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    current_streak, longest_streak = streaks(days)
    languages, total_bytes = language_totals(repos)
    total_bytes = total_bytes or 1

    width, height = 1100, 300
    cells = [
        ("KONTRIBUSI", contributions, "setahun terakhir"),
        ("COMMIT", commits, "setahun terakhir"),
        ("REPOSITORI", repo_count, "publik"),
        ("STREAK", current_streak, f"hari · rekor {longest_streak}"),
        ("STARS", stars, "dari repo publik"),
        ("FOLLOWERS", followers, "di GitHub"),
    ]

    parts: list[str] = []
    add = parts.append

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Kartu statistik GitHub {html.escape(user.get("name") or LOGIN)}">'
    )
    add(
        "<defs>"
        f'<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>'
        f'<stop offset="0.45" stop-color="{ACCENT}" stop-opacity="0.5"/>'
        f'<stop offset="1" stop-color="#22D3EE" stop-opacity="0"/>'
        "</linearGradient>"
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="1" fill="{GRID}"/></pattern>'
        "</defs>"
    )
    add(f'<rect width="{width}" height="{height}" rx="18" fill="{BG}"/>')
    add(f'<rect width="{width}" height="{height}" rx="18" fill="url(#dots)"/>')
    add(
        f'<rect x="24" y="0" width="{width - 48}" height="2" rx="1" fill="url(#beam)"/>'
    )
    add(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="18" '
        f'fill="none" stroke="{GRID}"/>'
    )

    # Header
    add(pacman(44, 40, 16))
    add(
        f'<text x="62" y="45" fill="{ACCENT}" font-family="ui-monospace, Consolas, monospace" '
        f'font-size="11" font-weight="700" letter-spacing="3">PLAYER CARD</text>'
    )
    add(
        f'<text x="36" y="78" fill="{TEXT}" font-family="ui-monospace, Consolas, monospace" '
        f'font-size="19" font-weight="700" letter-spacing="1.4">'
        f'{html.escape((user.get("name") or LOGIN).upper())}</text>'
    )
    add(
        f'<text x="36" y="98" fill="{MUTED}" font-family="ui-monospace, Consolas, monospace" '
        f'font-size="11" letter-spacing="1.2">@{html.escape(user.get("login") or LOGIN)}'
        f" · UNIVERSITAS KOMPUTER INDONESIA</text>"
    )

    # Enam sel statistik, 2 baris x 3 kolom
    mono = "ui-monospace, Consolas, monospace"
    for index, (label, value, note) in enumerate(cells):
        col, row = index % 3, index // 3
        x = 36 + col * 212
        y_value = 150 + row * 66
        add(
            f'<text x="{x}" y="{y_value}" fill="{TEXT}" font-family="{mono}" '
            f'font-size="30" font-weight="700">{fmt(int(value))}</text>'
        )
        add(
            f'<text x="{x + 2}" y="{y_value + 17}" fill="{ACCENT}" font-family="{mono}" '
            f'font-size="9" font-weight="700" letter-spacing="1.8">{label}</text>'
        )
        add(
            f'<text x="{x + 2}" y="{y_value + 31}" fill="{MUTED}" font-family="{mono}" '
            f'font-size="8.5" letter-spacing="0.6">{note}</text>'
        )

    # Pemisah vertikal
    add(f'<line x1="700" y1="30" x2="700" y2="270" stroke="{GRID}" stroke-width="1.5"/>')
    add(
        f'<text x="736" y="45" fill="{TEXT}" font-family="{mono}" font-size="11" '
        f'font-weight="700" letter-spacing="3">TOP LANGUAGES</text>'
    )

    for index, (name, size) in enumerate(languages):
        y = 74 + index * 38
        color = PALETTE[index % len(PALETTE)]
        percent = size / total_bytes * 100
        bar_width = 300
        filled = max(6.0, bar_width * percent / 100)
        add(
            f'<rect x="736" y="{y}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        add(
            f'<text x="754" y="{y + 9}" fill="{TEXT}" font-family="{mono}" font-size="11">'
            f"{html.escape(name)}</text>"
        )
        add(
            f'<text x="1064" y="{y + 9}" fill="{MUTED}" font-family="{mono}" font-size="10" '
            f'text-anchor="end">{percent:.1f}%</text>'
        )
        add(
            f'<rect x="736" y="{y + 16}" width="{bar_width}" height="5" rx="2.5" fill="{GRID}"/>'
        )
        add(
            f'<rect x="736" y="{y + 16}" width="{filled:.1f}" height="5" rx="2.5" fill="{color}"/>'
        )

    today = dt.date.today().isoformat()
    add(
        f'<text x="1064" y="{height - 16}" fill="{MUTED}" font-family="{mono}" font-size="9" '
        f'letter-spacing="1.2" text-anchor="end">UPDATED {today} · GITHUB API</text>'
    )
    add("</svg>")
    return "".join(parts)


def main() -> int:
    if not TOKEN:
        print("GITHUB_TOKEN tidak diset.", file=sys.stderr)
        return 1

    data = graphql(QUERY, {"login": LOGIN})
    svg = build_svg(data)

    output = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "stats.svg")
    output = os.path.abspath(output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(svg + "\n")

    print(f"stats.svg ditulis ke {output} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
