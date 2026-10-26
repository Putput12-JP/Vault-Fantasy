#!/usr/bin/env python3
"""
Does the page's matchupIdx / matchupTerm (nba/ui/projections.template.html) equal pricing.py matchup_idx / matchup_term? Runs the page's own JS in node on the
real data/diet_defense.json for every player against every opponent, both stats, and compares to 1e-9.   python3 nba/scripts/check_matchup_js_parity.py
"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pricing as PX

TPL = os.path.join(HERE, '..', 'ui', 'projections.template.html')
src = open(TPL).read()
js = src[src.index('// MATCHUP-IDX-START'):src.index('// MATCHUP-IDX-END')]
dd = json.load(open(os.path.join(HERE, '..', 'data', 'diet_defense.json')))
mt = json.load(open(os.path.join(HERE, '..', 'data', 'matchup_terms.json')))
ta_path = os.path.join(HERE, '..', 'data', 'team_allowance.json')
ta = json.load(open(ta_path)) if os.path.exists(ta_path) else None          # build it first: python3 nba/scripts/build_team_allowance.py [--season N]
pr = PX.Pricer.__new__(PX.Pricer)
pr.DDF, pr.MT, pr.TA, pr.example = dd, mt, ta, False
pairs = [(pid, t, s) for pid in dd['players'] for t in dd['teams'] for s in ('3pm', 'ast')]
if ta:
    pairs += [('0', t, s) for t in ta['teams'] for s in ('pts', 'reb')]       # team-level stats do not depend on the player
py = [(pr.matchup_idx(pid, t, s), pr.matchup_term(pid, t, s, 2.5)) for pid, t, s in pairs]
prog = f"""const DD = {json.dumps(dd)}; const MT = {json.dumps(mt)}; const TA = {json.dumps(ta)};
{js}
const pairs = {json.dumps(pairs)};
console.log(JSON.stringify(pairs.map(([p, t, s]) => [matchupIdx(DD, MT, p, t, s), matchupTerm(p, t, s, 2.5)])));"""
with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
    f.write(prog)
out = json.loads(subprocess.run(['node', f.name], capture_output=True, text=True, check=True).stdout)
bad = 0
for (pi, pt), (ji, jt), k in zip(py, out, pairs):
    if (pi is None) != (ji is None) or (pi is not None and abs(pi - ji) > 1e-9) or abs(pt - jt) > 1e-9:
        bad += 1
        if bad <= 5:
            print('MISMATCH', k, pi, ji, pt, jt)
defined = sum(1 for a, _ in py if a is not None)
print(f'{len(pairs)} player x opponent x stat checks, {defined} with an index, {bad} mismatches')
sys.exit(1 if bad else 0)
