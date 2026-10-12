#!/usr/bin/env python3
"""Refresh cfb_logos.json: normalised team name -> ESPN team id, for the Sharp Money share card.

ESPN serves every college logo at a.espncdn.com/i/teamlogos/ncaa/500/<id>.png, but Sharp Money's CFB
payload only carries names, so the card needs a name -> id table. Run, then python3 patch_index.py.
OVERRIDES holds the names where Action Network and ESPN disagree. Anything still unmapped falls back
to a team-colour monogram on the card, so a miss costs a logo, never the card.
"""
import json, os, re, unicodedata, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000'
OVERRIDES = {  # Sharp Money name -> ESPN id
    "North Carolina State Wolfpack": 152, "UMass Minutemen": 113, "Hawai'i Warriors": 62, "Tennessee Volunteers": 2633,
    "Appalachian State Mountaineers": 2026, "Sam Houston State Bearkats": 2534,
}

def norm(s):
    s = unicodedata.normalize('NFD', s or '')
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower())

req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
teams = [t['team'] for t in json.load(urllib.request.urlopen(req))['sports'][0]['leagues'][0]['teams']]
out = {norm(t['displayName']): int(t['id']) for t in teams}
for k, v in OVERRIDES.items(): out[norm(k)] = v
json.dump(out, open(os.path.join(HERE, 'cfb_logos.json'), 'w'), separators=(',', ':'), sort_keys=True)
print(len(out), 'teams')
