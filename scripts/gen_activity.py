#!/usr/bin/env python3
"""Generate a tokyonight contribution-activity area chart as a self-contained SVG.

Fetches the user's daily public contribution counts via the GitHub GraphQL API
and renders an area/line chart. Committed into the repo so it renders on the
profile even when GitHub's external-image proxy (camo) is disabled.

Env:
  GITHUB_TOKEN / GH_TOKEN : token for the GraphQL API
  GH_LOGIN                : GitHub username (default: tanujkart)
  DAYS                    : days of history to plot (default: 30)
"""
import json, os, sys, urllib.request

LOGIN = os.environ.get("GH_LOGIN", "tanujkart")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
DAYS = int(os.environ.get("DAYS", "30"))
OUT = os.environ.get("OUT", "activity.svg")

if not TOKEN:
    sys.exit("ERROR: no GITHUB_TOKEN/GH_TOKEN in environment")

# --- tokyonight palette ---
BG    = "#1a1b27"
BORDER= "#2a2b3c"
TITLE = "#e4e2e2"
LINE  = "#70a5fd"
POINT = "#bf91f3"
MUTED = "#8b90a8"

def fetch_days():
    q = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            weeks{ contributionDays{ date contributionCount } }
          }
        }
      }
    }"""
    body = json.dumps({"query": q, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "activity-graph-generator"})
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    if "errors" in resp:
        sys.exit("GraphQL errors: " + json.dumps(resp["errors"]))
    weeks = resp["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:]

def catmull_rom(pts):
    """Return an SVG path 'd' string smoothing through pts via Catmull-Rom -> Bezier."""
    if len(pts) < 2:
        return ""
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i-1] if i > 0 else pts[i]
        p1 = pts[i]
        p2 = pts[i+1]
        p3 = pts[i+2] if i + 2 < len(pts) else pts[i+1]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d += f" C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d

def render(days):
    W, H = 840, 280
    L, R, T, B = 46, W - 24, 70, H - 34   # chart bounds
    counts = [d["contributionCount"] for d in days]
    n = len(days)
    total = sum(counts)
    mx = max(counts) if counts and max(counts) > 0 else 1

    def X(i): return L + (R - L) * (i / (n - 1)) if n > 1 else (L + R) / 2
    def Y(v): return B - (B - T) * (v / mx)

    pts = [(X(i), Y(counts[i])) for i in range(n)]
    line_d = catmull_rom(pts)
    area_d = line_d + f" L {pts[-1][0]:.1f} {B} L {pts[0][0]:.1f} {B} Z"

    # x-axis date ticks (first / mid / last)
    ticks = []
    for i in (0, n // 2, n - 1):
        label = days[i]["date"][5:]  # MM-DD
        ticks.append((X(i), label))

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img" aria-label="Contribution activity graph">')
    s.append('<defs>'
             f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{LINE}" stop-opacity="0.42"/>'
             f'<stop offset="1" stop-color="{LINE}" stop-opacity="0"/>'
             '</linearGradient></defs>')
    s.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" ry="10" '
             f'fill="{BG}" stroke="{BORDER}"/>')
    # title
    s.append(f'<text x="24" y="36" fill="{TITLE}" font-family="-apple-system,Segoe UI,'
             f'Helvetica,Arial,sans-serif" font-size="19" font-weight="600">Contribution Graph</text>')
    s.append(f'<text x="{R}" y="36" fill="{MUTED}" font-family="-apple-system,Segoe UI,'
             f'Helvetica,Arial,sans-serif" font-size="13" text-anchor="end">'
             f'{total} contributions · last {n} days</text>')
    # baseline
    s.append(f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" stroke="{BORDER}"/>')
    # area + line
    s.append(f'<path d="{area_d}" fill="url(#area)"/>')
    s.append(f'<path d="{line_d}" fill="none" stroke="{LINE}" stroke-width="2.5" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')
    # points
    for (px, py) in pts:
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="{POINT}"/>')
    # x labels
    for (tx, label) in ticks:
        s.append(f'<text x="{tx:.1f}" y="{B+20}" fill="{MUTED}" font-family="-apple-system,'
                 f'Segoe UI,Helvetica,Arial,sans-serif" font-size="12" text-anchor="middle">{label}</text>')
    s.append('</svg>')
    return "\n".join(s)

days = fetch_days()
svg = render(days)
with open(OUT, "w") as f:
    f.write(svg)
print(f"wrote {OUT}: {len(days)} days, {sum(d['contributionCount'] for d in days)} contributions")
