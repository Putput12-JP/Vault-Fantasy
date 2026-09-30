#!/usr/bin/env python3
"""
Official NBA injury reports, archived as PDFs, parsed to "status as of time T".

The league posts a report hourly (every 15 min from late 2025) and the old ones
stay online at
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HHPM.pdf      (older)
  https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMPM.pdf   (newer)

This is what lets a backtest know who was OUT / QUESTIONABLE when a line was
set, instead of reading the final box score (which leaks the future).

For every game date in the hoopR schedule we pull SNAPSHOT_HOURS (ET), which
covers a morning line and the report just before each tip slot.

Needs pdfplumber, which is not stdlib: run with the project venv
  nba/.venv/bin/python nba/scripts/fetch_injury_reports.py 2025 2026

Writes (raw/ is gitignored)
  nba/raw/injuries/pdf/<date>_<HHMM>.pdf
  nba/raw/injuries/reports_<season>.jsonl  one row per player per snapshot:
     {report_et, game_date, tip_et, matchup, team, player, status, reason}
"""
import csv, datetime as dt, json, os, re, subprocess, sys, time

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
OUT = os.path.join(RAW, 'injuries')
PDF = os.path.join(OUT, 'pdf')
URL = 'https://ak-static.cms.nba.com/referee/injury/Injury-Report_'
SNAPSHOT_HOURS = [11, 13, 15, 17, 18, 19, 20, 21, 22]  # ET, 24h
# The NBA CDN (Akamai) 403s EVERY file for a while after a burst: 8 parallel
# workers got us blocked within ~40 files. One request at a time with a pause,
# and stop the run on a streak of 403s rather than extend the block.
PAUSE_S = 1.5
MAX_403_STREAK = 8


class Blocked(Exception):
    pass
KEEP_TYPES = {'STD', 'CC', 'RD16', 'QTR', 'SEMI', 'FINAL'}
STATUSES = {'Out', 'Questionable', 'Doubtful', 'Probable', 'Available'}
COLS = ['GameDate', 'GameTime', 'Matchup', 'Team', 'PlayerName', 'CurrentStatus', 'Reason']


NEW_NAMES_FROM = '2025-12-01'  # ~when files switched to _HH_MMPM; try the likely name first (each miss costs a paced request)


def names(day, hour):
    h12 = hour % 12 or 12
    ap = 'AM' if hour < 12 else 'PM'
    new, old = f'{day}_{h12:02d}_00{ap}', f'{day}_{h12:02d}{ap}'
    return [new, old] if day >= NEW_NAMES_FROM else [old, new]


def download(job):
    day, hour = job
    dest = os.path.join(PDF, f'{day}_{hour:02d}00.pdf')
    if os.path.exists(dest):
        return dest
    codes = []
    for n in names(day, hour):
        time.sleep(PAUSE_S)
        p = subprocess.run(['curl', '-s', '--max-time', '40', '-o', dest + '.part', '-w', '%{http_code}', URL + n + '.pdf'],
                           capture_output=True, text=True)
        codes.append(p.stdout)
        if p.stdout == '200':
            os.replace(dest + '.part', dest)
            return dest
    if os.path.exists(dest + '.part'):
        os.remove(dest + '.part')
    # A missing file is a 403 on this CDN too, so only "every name 403'd" counts toward the streak.
    return 'blocked?' if all(c == '403' for c in codes) else None


def parse(path):
    import pdfplumber
    rows, ctx = [], {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            hdr = {w['text']: w['x0'] for w in words if w['text'] in COLS}
            if len(hdr) < len(COLS):
                hdr = ctx.get('_hdr') or hdr
            if len(hdr) < len(COLS):
                continue
            ctx['_hdr'] = hdr
            edges = sorted((x, c) for c, x in hdr.items())
            lines = {}
            for w in words:
                if w['top'] < 100 or w['text'] in COLS or w['text'].startswith('Page'):
                    continue
                col = edges[0][1]
                for x, c in edges:
                    if w['x0'] >= x - 3:
                        col = c
                lines.setdefault(round(w['top']), {}).setdefault(col, []).append(w['text'])
            page_rows = []
            for top in sorted(lines):
                ln = lines[top]
                for c in ('GameDate', 'GameTime', 'Matchup', 'Team'):
                    if c in ln:
                        ctx[c] = ' '.join(ln[c])
                if 'PlayerName' in ln and 'CurrentStatus' in ln:
                    st = ln['CurrentStatus'][0]
                    if st in STATUSES:
                        page_rows.append({'top': top, 'game_date': ctx.get('GameDate'), 'tip_et': ctx.get('GameTime'),
                                          'matchup': ctx.get('Matchup'), 'team': ctx.get('Team'),
                                          'player': ' '.join(ln['PlayerName']), 'status': st,
                                          'reason': ' '.join(ln.get('Reason', []))})
                elif 'Reason' in ln and page_rows is not None:
                    pass
            # reason text wraps above/below its player row: attach to the nearest row
            for top in sorted(lines):
                ln = lines[top]
                if 'Reason' in ln and 'PlayerName' not in ln and page_rows:
                    near = min(page_rows, key=lambda r: abs(r['top'] - top))
                    if abs(near['top'] - top) <= 12:
                        near['reason'] = (near['reason'] + ' ' + ' '.join(ln['Reason'])).strip()
            for r in page_rows:
                r.pop('top')
            rows += page_rows
    return rows


def game_days(season):
    days = set()
    for g in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'schedule_{season}.csv'))):
        if g['status_type_completed'] == 'true' and g['type_abbreviation'] in KEEP_TYPES:
            d = dt.datetime.fromisoformat(g['date'].replace('Z', '+00:00')) - dt.timedelta(hours=5)
            days.add(d.date().isoformat())
    return sorted(days)


def main(argv):
    seasons = [int(a) for a in argv if a.isdigit()] or [2025, 2026]
    os.makedirs(PDF, exist_ok=True)
    for s in seasons:
        days = game_days(s)
        jobs = [(d, h) for d in days for h in SNAPSHOT_HOURS]
        got, streak = [], 0
        for j in jobs:
            p = download(j)
            if p == 'blocked?':
                streak += 1
                if streak >= MAX_403_STREAK:
                    print(f'{s}: {streak} straight 403s at {j}; CDN is blocking, stopping. Re-run later (resumes).', flush=True)
                    break
                continue
            streak = 0
            if p:
                got.append((j, p))
        got += [((d, h), os.path.join(PDF, f'{d}_{h:02d}00.pdf')) for d, h in jobs
                if (d, h) not in {g[0] for g in got} and os.path.exists(os.path.join(PDF, f'{d}_{h:02d}00.pdf'))]
        got.sort()
        print(f'{s}: {len(days)} game days, {len(got)}/{len(jobs)} reports downloaded', flush=True)
        out = os.path.join(OUT, f'reports_{s}.jsonl')
        n = bad = 0
        with open(out, 'w') as f:
            for (day, hour), p in got:
                try:
                    rows = parse(p)
                except Exception:
                    bad += 1
                    continue
                for r in rows:
                    r['report_et'] = f'{day}T{hour:02d}:00'
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')
                    n += 1
        print(f'{s}: {n} player-status rows, {bad} unreadable PDFs', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
