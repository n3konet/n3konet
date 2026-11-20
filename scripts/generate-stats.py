import datetime
import json
import os
import re
import urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

USERNAME = os.environ["USERNAME"]
TOKEN = os.environ["GH_TOKEN"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

THEMES = {
    "dark": {
        "bg": "#16151C",
        "text": "#F4F3F8",
        "muted": "#9E9AA8",
        "accent": "#BFA8FF",
        "bars": ("#BFA8FF", "#8B6CE8", "#5B4699", "#362C54"),
        "track": "#231E33",
    },
    "light": {
        "bg": "#F4F2F8",
        "text": "#18161F",
        "muted": "#5D5968",
        "accent": "#6D4AFF",
        "bars": ("#6D4AFF", "#9B82FF", "#C8B6FF", "#DFD6FA"),
        "track": "#ECE6FC",
    },
}


def fetch_stats():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USERNAME,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        payload = json.load(res)

    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")

    user = payload["data"]["user"]
    contrib = user["contributionsCollection"]
    commits = contrib["totalCommitContributions"] + contrib["restrictedContributionsCount"]
    repos = user["repositories"]["totalCount"]
    nodes = user["repositories"]["nodes"]
    stars = sum(n["stargazerCount"] for n in nodes)

    lang_bytes = defaultdict(int)
    for n in nodes:
        for edge in n["languages"]["edges"]:
            name = edge["node"]["name"]
            if name.lower() != "tex":
                lang_bytes[name] += edge["size"]

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:4]
    langs = [(name, round(size / total_bytes * 100)) for name, size in top_langs]

    return commits, stars, repos, langs


def render_svg(c, commits, stars, repos, langs):
    bar_w, x_cursor = 340, 0
    bar_rects, legend_items = [], []
    total_pct = sum(pct for _, pct in langs) or 1

    for i, (name, pct) in enumerate(langs):
        seg_w = max(8, round((pct / total_pct) * bar_w))
        if i == len(langs) - 1:
            seg_w = max(0, bar_w - x_cursor)
        color = c["bars"][i % len(c["bars"])]
        bar_rects.append(f'<rect x="{x_cursor}" y="0" width="{seg_w}" height="10" fill="{color}"/>')
        x_cursor += seg_w

        lx, ly = (i % 2) * 182, (i // 2) * 20
        legend_items.append(
            f'<g transform="translate({lx},{ly})">'
            f'<circle cx="4" cy="-4" r="3.5" fill="{color}"/>'
            f'<text x="14" y="0" class="s" font-size="12.5" font-weight="500" fill="{c["text"]}">{name}</text>'
            f'<text x="158" y="0" text-anchor="end" class="s" font-size="12" fill="{c["muted"]}">{pct}%</text>'
            f"</g>"
        )

    # 6px gap (397..403) | Left: TL=0, TR=8, BR=8, BL=28 | Right: TL=8, TR=0, BR=28, BL=8
    left_card = "M0 0H389A8 8 0 0 1 397 8V124A8 8 0 0 1 389 132H28A28 28 0 0 1 0 104Z"
    right_card = "M411 0H800V104A28 28 0 0 1 772 132H411A8 8 0 0 1 403 124V8A8 8 0 0 1 411 0Z"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 132" width="800" height="132" role="img" aria-label="GitHub Stats">'
        f'<defs><style>.s{{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,Helvetica,Arial,sans-serif}}</style>'
        f'<clipPath id="b"><rect width="{bar_w}" height="10" rx="5"/></clipPath></defs>'
        f'<path d="{left_card}" fill="{c["bg"]}"/>'
        f'<text x="28" y="34" class="s" font-size="12" font-weight="600" fill="{c["muted"]}" letter-spacing=".4">OVERVIEW</text>'
        f'<g transform="translate(28,82)">'
        f'<text class="s" font-size="28" font-weight="600" fill="{c["accent"]}" letter-spacing="-.6">{commits}</text>'
        f'<text y="20" class="s" font-size="12.5" fill="{c["muted"]}">Commits (1y)</text>'
        f'<text x="124" class="s" font-size="28" font-weight="600" fill="{c["text"]}" letter-spacing="-.6">{stars}</text>'
        f'<text x="124" y="20" class="s" font-size="12.5" fill="{c["muted"]}">Stars</text>'
        f'<text x="230" class="s" font-size="28" font-weight="600" fill="{c["text"]}" letter-spacing="-.6">{repos}</text>'
        f'<text x="230" y="20" class="s" font-size="12.5" fill="{c["muted"]}">Public repos</text>'
        f'</g>'
        f'<path d="{right_card}" fill="{c["bg"]}"/>'
        f'<text x="431" y="34" class="s" font-size="12" font-weight="600" fill="{c["muted"]}" letter-spacing=".4">LANGUAGES</text>'
        f'<g transform="translate(431,52)">'
        f'<rect width="{bar_w}" height="10" rx="5" fill="{c["track"]}"/>'
        f'<g clip-path="url(#b)">{"".join(bar_rects)}</g>'
        f'</g>'
        f'<g transform="translate(431,86)">{"".join(legend_items)}</g>'
        f'</svg>\n'
    )


def update_age(today):
    raw = os.environ.get("BIRTHDAY", "").strip()
    if not raw:
        return False

    try:
        bday = datetime.date.fromisoformat(raw)
    except ValueError:
        return False

    age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

    changed = False
    for theme in ("dark", "light"):
        path = f"assets/about-{theme}.svg"
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            old = f.read()

        svg = re.sub(r"\b\d+-year-old\b", f"{age}-year-old", old)
        svg = re.sub(r"(>Age</text>\s*<text[^>]*>)\d+(</text>)", rf"\g<1>{age}\g<2>", svg)

        if svg != old:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            changed = True

    return changed


def main():
    now = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    commits, stars, repos, langs = fetch_stats()
    os.makedirs("assets", exist_ok=True)

    changed = update_age(now.date())
    for theme, palette in THEMES.items():
        path = f"assets/stats-{theme}.svg"
        svg = render_svg(palette, commits, stars, repos, langs)
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        if svg != old:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            changed = True

    if changed or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        today = now.strftime("%d/%m/%Y")
        with open("README.md", encoding="utf-8") as f:
            readme = f.read()
        updated = re.sub(
            r"(<!-- LAST_UPDATED:START -->).*?(<!-- LAST_UPDATED:END -->)",
            f"\\1Updated {today}\\2",
            readme,
            flags=re.S,
        )
        if updated != readme:
            with open("README.md", "w", encoding="utf-8") as f:
                f.write(updated)


if __name__ == "__main__":
    main()