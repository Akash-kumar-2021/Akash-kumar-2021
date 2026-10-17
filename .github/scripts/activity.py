"""Render assets/activity.svg from the GitHub contribution calendar.

Usage: GITHUB_TOKEN=... python activity.py <username> <output.svg>
"""
import datetime as dt
import json
import os
import sys
import urllib.request

from svgkit import Doc, measure, BG, PANEL, LINE, HAIR, TEXT, SUB, MUTED, ACC

RAMP = ["#1A222C", "#0E3B2C", "#007867", "#00A76F", ACC]
QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){createdAt
 repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount}
 contributionsCollection(from:$from,to:$to){totalCommitContributions totalPullRequestContributions
 contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def gql(variables):
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": variables}).encode(),
                                 headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": "profile-activity"})
    body = json.load(urllib.request.urlopen(req, timeout=30))
    if body.get("errors"):
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def fetch(login):
    today = dt.date.today()
    first = gql({"login": login, "from": f"{today.year}-01-01T00:00:00Z", "to": f"{today.isoformat()}T23:59:59Z"})
    start_year = int(first["createdAt"][:4])
    days, years, commits = {}, {}, 0
    for y in range(start_year, today.year + 1):
        end = today if y == today.year else dt.date(y, 12, 31)
        c = gql({"login": login, "from": f"{y}-01-01T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"})["contributionsCollection"]
        years[y] = c["contributionCalendar"]["totalContributions"]
        commits += c["totalCommitContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    # rolling last 12 months, aligned to weeks starting Sunday
    end = today
    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    recent = gql({"login": login, "from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"})["contributionsCollection"]
    for w in recent["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    return {"created": first["createdAt"][:10], "repos": first["repositories"]["totalCount"], "days": days,
            "years": years, "commits": commits, "start": start, "end": end}


def streaks(days, today):
    longest = run = 0
    for d in sorted(days):
        run = run + 1 if days[d] else 0
        longest = max(longest, run)
    cur, d = 0, today
    if not days.get(d):
        d -= dt.timedelta(days=1)
    while days.get(d):
        cur += 1; d -= dt.timedelta(days=1)
    return cur, longest


def fmt(n):
    return f"{n:,}"


def render(data, out):
    days, today = data["days"], data["end"]
    total = sum(data["years"].values())
    cur, longest = streaks(days, today)
    best_day = max(days, key=lambda k: (days[k], k))
    active = [d for d, n in days.items() if n]
    since = dt.date.fromisoformat(data["created"])
    weekday = [0] * 7
    for d, n in days.items():
        weekday[(d.weekday() + 1) % 7] += n

    W = 1200
    doc = Doc(W, 10, f"GitHub activity: {total} contributions since {since.year}, {data['commits']} commits, longest streak {longest} days")
    doc.css += [".fu{opacity:0;animation:fu .8s cubic-bezier(.2,.7,.2,1) forwards}@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}",
                ".bar{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);animation:grow 1.1s cubic-bezier(.2,.7,.2,1) forwards}@keyframes grow{to{transform:scaleY(1)}}",
                ".hbar{transform-box:fill-box;transform-origin:0 50%;transform:scaleX(0);animation:hgrow 1s cubic-bezier(.2,.7,.2,1) forwards}@keyframes hgrow{to{transform:scaleX(1)}}",
                ".cell{opacity:0;animation:ci .5s ease forwards}@keyframes ci{to{opacity:1}}",
                ".pulse{animation:pl 2.2s ease-in-out infinite}@keyframes pl{50%{opacity:.35}}"]

    def panel(x, y, w, h, label, right=None, delay=0):
        s = (f'<g class="fu" style="animation-delay:{delay:.2f}s"><rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="12" fill="{PANEL}" stroke="{LINE}"/>'
             + doc.text(label, 12, x + 24, y + 34, "mono", 500, 1.6, fill=MUTED))
        if right:
            s += doc.text(right, 12, x + w - 24, y + 34, "mono", 500, 1.2, anchor="end", fill=SUB)
        return s + "</g>"

    # KPI tiles
    kpis = [(fmt(total), "CONTRIBUTIONS", f"since {since.strftime('%B %Y')}"),
            (fmt(data["commits"]), "COMMITS", f"across {data['repos']} public repositories"),
            (f"{longest}", "LONGEST STREAK", f"days in a row · current {cur}"),
            (f"{days[best_day]}", "BEST DAY", best_day.strftime("contributions on %b %d, %Y").replace(" 0", " "))]
    kw, gap, y = (W - 3 * 16) / 4, 16, 0
    for i, (val, lab, sub) in enumerate(kpis):
        x = i * (kw + gap)
        doc.add(panel(x, y, kw, 132, lab, delay=.1 + i * .1))
        doc.add(f'<g class="fu" style="animation-delay:{.25 + i * .1:.2f}s">' + doc.text(val, 46, x + 24, y + 92, "sans", 600, -1.2, fill=TEXT)
                + doc.text(sub, 14, x + 24, y + 116, "sans", 400, fill=SUB) + "</g>")
        if i == 0:
            doc.add(f'<circle cx="{x + kw - 30}" cy="{y + 30}" r="4" fill="{ACC}" class="pulse"/>')

    # contributions by year
    y = 132 + 20
    lw, rw, ph = 724, W - 724 - 16, 290
    yrs = sorted(data["years"])
    peak = max(data["years"].values()) or 1
    doc.add(panel(0, y, lw, ph, "CONTRIBUTIONS BY YEAR", f"PEAK {max(yrs, key=lambda k: data['years'][k])}", .5))
    cx0, base, ch = 40, y + ph - 44, ph - 120
    slot = (lw - 80) / len(yrs)
    bw = min(64, slot * .56)
    doc.add(f'<rect x="24" y="{base + .5}" width="{lw - 48}" height="1" fill="{LINE}"/>')
    for i, yr in enumerate(yrs):
        n = data["years"][yr]
        h = max(3, ch * n / peak)
        bx = cx0 + i * slot + (slot - bw) / 2
        top = n == peak
        doc.add(f'<rect class="bar" style="animation-delay:{.7 + i * .08:.2f}s" x="{bx:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="5" '
                f'fill="{ACC if top else "#2A6B52"}" fill-opacity="{1 if top else .85}"/>')
        doc.add(f'<g class="fu" style="animation-delay:{1.2 + i * .08:.2f}s">' + doc.text(str(n), 15, bx + bw / 2, base - h - 12, "sans", 600, anchor="middle", fill=TEXT if top else SUB) + "</g>")
        doc.add(doc.text(str(yr), 13, bx + bw / 2, base + 26, "mono", 400, .5, anchor="middle", fill=MUTED))

    # by weekday
    names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    wx = lw + 16
    wpeak = max(weekday) or 1
    doc.add(panel(wx, y, rw, ph, "BY WEEKDAY", f"MOST ACTIVE {names[weekday.index(wpeak)]}", .6))
    for i, n in enumerate(weekday):
        ry = y + 66 + i * 30
        full = rw - 48 - 46 - 50
        top = n == wpeak
        doc.add(doc.text(names[i], 12, wx + 24, ry + 10, "mono", 500, 1, fill=SUB if top else MUTED))
        doc.add(f'<rect x="{wx + 70}" y="{ry}" width="{full}" height="12" rx="6" fill="#1A222C"/>')
        doc.add(f'<rect class="hbar" style="animation-delay:{.8 + i * .06:.2f}s" x="{wx + 70}" y="{ry}" width="{max(6, full * n / wpeak):.1f}" height="12" rx="6" fill="{ACC if top else "#2A6B52"}"/>')
        doc.add(doc.text(str(n), 13, wx + rw - 24, ry + 11, "sans", 500, anchor="end", fill=TEXT if top else SUB))

    # heatmap, last 12 months
    y += ph + 20
    cell, cg = 15, 4
    weeks = []
    d = data["start"]
    while d <= today:
        weeks.append([d + dt.timedelta(days=k) for k in range(7)])
        d += dt.timedelta(days=7)
    gw = len(weeks) * (cell + cg) - cg
    hh = 7 * (cell + cg) + 120
    last_year = sum(days.get(x, 0) for wk in weeks for x in wk if x <= today)
    act = sum(1 for wk in weeks for x in wk if x <= today and days.get(x))
    doc.add(panel(0, y, W, hh, "LAST 12 MONTHS", f"{last_year} CONTRIBUTIONS · {act} ACTIVE DAYS", .7))
    gx = (W - gw) / 2 + 14
    gy = y + 76
    seen = set()
    for wi, wk in enumerate(weeks):
        m = wk[0]
        if wk[0].day <= 7 and (m.year, m.month) not in seen:
            seen.add((m.year, m.month))
            doc.add(doc.text(m.strftime("%b").upper(), 11, gx + wi * (cell + cg), gy - 12, "mono", 400, .8, fill=MUTED))
        cells = []
        for di, x in enumerate(wk):
            if x > today:
                continue
            n = days.get(x, 0)
            lvl = 0 if n == 0 else 1 if n == 1 else 2 if n <= 3 else 3 if n <= 6 else 4
            cells.append(f'<rect x="{gx + wi * (cell + cg)}" y="{gy + di * (cell + cg)}" width="{cell}" height="{cell}" rx="3.5" fill="{RAMP[lvl]}"/>')
        doc.add(f'<g class="cell" style="animation-delay:{.9 + wi * .018:.2f}s">{"".join(cells)}</g>')
    for i, lab in ((1, "MON"), (3, "WED"), (5, "FRI")):
        doc.add(doc.text(lab, 11, gx - 12, gy + i * (cell + cg) + 11.5, "mono", 400, .8, anchor="end", fill=MUTED))
    ly = gy + 7 * (cell + cg) + 18
    lx = gx + gw - 5 * (cell + cg) - measure("MORE", 11, "mono", 400, .8) - 8
    doc.add(doc.text("LESS", 11, lx - 10, ly + 11.5, "mono", 400, .8, anchor="end", fill=MUTED))
    doc.add("".join(f'<rect x="{lx + i * (cell + cg)}" y="{ly}" width="{cell}" height="{cell}" rx="3.5" fill="{c}"/>' for i, c in enumerate(RAMP)))
    doc.add(doc.text("MORE", 11, lx + 5 * (cell + cg) + 6, ly + 11.5, "mono", 400, .8, fill=MUTED))
    doc.add(doc.text(f"UPDATED {today.strftime('%d %b %Y').upper()}", 11, gx, ly + 11.5, "mono", 400, .8, fill=MUTED))

    doc.h = int(y + hh + 2)
    doc.save(out)


if __name__ == "__main__":
    render(fetch(sys.argv[1]), os.path.abspath(sys.argv[2]))
