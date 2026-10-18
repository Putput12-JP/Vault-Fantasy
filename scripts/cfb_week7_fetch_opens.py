#!/usr/bin/env python3
"""ESPN opening spreads (DraftKings) for every 2022-2025 game in <dir>/base_rows.csv, same field fetch_espn_opens.py reads for 2026.
Writes <dir>/opens_hist.json {game_id: {so, ouo}} (so = home spread, + = home underdog). Run: python3 scripts/cfb_week7_fetch_opens.py --dir /tmp/cfbstudy"""
import argparse, json, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_espn_opens as fe

ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
ids = [int(i) for i in pd.read_csv(os.path.join(a.dir, 'base_rows.csv')).game_id]
with ThreadPoolExecutor(8) as ex: res = list(ex.map(fe.one, ids))
out = {str(i): d for i, d, e in res if d and d['so'] is not None}
json.dump(out, open(os.path.join(a.dir, 'opens_hist.json'), 'w')); print(len(ids), 'games,', len(out), 'with an open')
