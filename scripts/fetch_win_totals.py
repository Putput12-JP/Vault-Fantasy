#!/usr/bin/env python3
"""Preseason FBS season win totals (the market's own preseason number), one file per season: data/win_totals/win_totals_<year>.json.

Why: the CFB model's preseason prior is a regression on talent, returning production, recruiting and the portal. The market's season win totals are a preseason read that already
prices all of that. docs/retro/cfb-week-7.md (round 6) left a win-total prior as the one untested market-prior idea, and the totals are not available from a free API, so they are
read once a season from two public pages and stored here with the source. No number is estimated: a team the page does not list is simply absent.

  2022-2025  SportsBettingDime's historical win totals page (opening totals and odds; its 2023 and 2024 tables list about 70 teams, 2022 about 80, 2025 all 133)
  2026+      Sharp Football Analysis's season win totals table (the page lists the teams it carries; coverage is recorded in the file)

Run: python3 scripts/fetch_win_totals.py [--year 2026]        Stdlib only. Re-running overwrites that year's file with what the page shows now.
"""
import argparse, html, json, os, re, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'win_totals')
UA = 'Mozilla/5.0 (vault-fantasy win totals, one fetch per season)'
SBD = 'https://www.sportsbettingdime.com/college-football/futures/win-totals-best-odds/%d-season'
SFA = 'https://www.sharpfootballanalysis.com/betting/college-football-win-totals/'
ALIAS = {'Appalachian State': 'App State', 'Miami FL': 'Miami', 'Miami (FL)': 'Miami', 'Miami OH': 'Miami (OH)', 'Southern Mississippi': 'Southern Miss', 'Connecticut': 'UConn',
         'ULM': 'UL Monroe', 'Louisiana-Monroe': 'UL Monroe', 'Louisiana Monroe': 'UL Monroe', 'UT San Antonio': 'UTSA', 'San Jose State': 'San José State', 'Hawaii': "Hawai'i",
         'Sam Houston State': 'Sam Houston', 'North Carolina State': 'NC State', 'N.C. State': 'NC State', 'Pitt': 'Pittsburgh', 'Massachusetts': 'UMass', 'Florida International': 'FIU', 'UMass': 'Massachusetts', 'FIU': 'Florida International'}   # source name -> CollegeFootballData school name


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60).read().decode('utf-8', 'replace')


def tables(h):
    """every <table> as (text just before it, rows of cell text)"""
    out = []
    for m in re.finditer(r'<table.*?</table>', h, flags=re.S):
        rows = []
        for tr in re.findall(r'<tr.*?</tr>', m.group(0), flags=re.S):
            cells = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', c))).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, flags=re.S)]
            if cells: rows.append(cells)
        pre = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h[max(0, m.start() - 2500):m.start()])))
        out.append((pre, rows))
    return out


def num(s):
    m = re.match(r'^\s*(\d+(?:\.\d+)?)', str(s or '')); return float(m.group(1)) if m else None


def sbd_year(y):
    """the table whose lead-in names the season; the page also carries other seasons' tables, so the heading decides, never the position"""
    h = get(SBD % y); found = None
    for pre, rows in tables(h):
        if not rows or rows[0][:2] != ['Team', 'Win Total']: continue
        if re.search(r'%d College Football Win Totals' % y, pre[-600:]) or (y == 2022 and 'Over/Under Odds' in rows[0] and 'Georgia ran the table' in pre):
            found = rows; break
    if not found: return None
    teams = {}
    for r in found[1:]:
        if len(r) >= 2 and num(r[1]) is not None:
            odds = r[2:]; teams[r[0]] = dict(total=num(r[1]), odds=' / '.join(odds) if odds else None)
    return teams


def sfa_year():
    h = get(SFA); teams = {}
    for _, rows in tables(h):
        if not rows or 'Team' not in rows[0]: continue
        ti = rows[0].index('Team'); wi = next((i for i, c in enumerate(rows[0]) if 'Win Total' in c), None)
        if wi is None: continue
        for r in rows[1:]:
            if len(r) > max(ti, wi) and num(r[wi]) is not None: teams[r[ti]] = dict(total=num(r[wi]), odds=None)
    return teams


def match_ids(teams, year):
    ids = {t['school']: t['id'] for t in json.load(open(os.path.join(ROOT, 'data', 'cfbd', f'teams_fbs_{year}.json')))} if os.path.exists(os.path.join(ROOT, 'data', 'cfbd', f'teams_fbs_{year}.json')) else {}
    low = {k.lower(): v for k, v in ids.items()}; out, miss = {}, []
    for name, v in teams.items():
        key = ALIAS.get(name, name); tid = ids.get(key) or low.get(key.lower()) or ids.get(name) or low.get(name.lower())
        if tid is None: miss.append(name)
        else: out[str(tid)] = dict(v, team=name)
    return out, miss


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--year', type=int, action='append'); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for y in a.year or [2022, 2023, 2024, 2025, 2026]:
        teams = sfa_year() if y >= 2026 else sbd_year(y); time.sleep(1)
        if not teams: print(y, 'no table found; file left as it was'); continue
        by_id, miss = match_ids(teams, y)
        doc = dict(year=y, source=SFA if y >= 2026 else SBD % y, fetched=int(time.time()), listed=len(teams), matched=len(by_id), unmatched=sorted(miss),
                   note='Opening season win totals as listed by the source. A team the source does not list is absent, not estimated.', teams=by_id)
        json.dump(doc, open(os.path.join(OUT, f'win_totals_{y}.json'), 'w'), indent=1, sort_keys=True)
        print(y, 'listed', len(teams), 'matched', len(by_id), 'unmatched', sorted(miss)[:12])


if __name__ == '__main__':
    main()
