"""prop_hist.py: one row per poll, both sides of a poll folded together, unchanged polls dropped."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import prop_hist


def day(rows, metas):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, 'meta.jsonl'), 'w') as f:
        for m in metas:
            f.write(json.dumps(m) + '\n')
    with open(os.path.join(d, 'espn.jsonl'), 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    return d


def test_builds_series():
    k0, k1 = '401|100|77|1|0', '401|100|77|1|1'
    metas = [{'k': k0, 'src': 'espn', 'game': '401', 'athlete_id': 77, 'type': 'Total Points'},
             {'k': k1, 'src': 'espn', 'game': '401', 'athlete_id': 77, 'type': 'Total Points'},
             {'k': '401|100|77|218|1', 'src': 'espn', 'game': '401', 'athlete_id': 77, 'type': 'Points Milestones'}]
    rows = [{'t': 10, 'k': k0, 'v': [12.5, '-123']}, {'t': 10, 'k': k1, 'v': [12.5, '-103']},
            {'t': 20, 'k': '401|100|77|218|1', 'v': [15, '+200']},                 # milestones are not main lines
            {'t': 30, 'k': k0, 'v': [13.5, '-102']}, {'t': 30, 'k': k1, 'v': [13.5, '-125']},
            {'t': 40, 'k': k0, 'v': [13.5, '-102']}]                                  # no change: dropped
    d = day(rows, metas)
    assert prop_hist.build(d) == {'77|pts': [[10, 12.5, '-123', '-103'], [30, 13.5, '-102', '-125']]}
    assert prop_hist.write(d, now=50) == 1
    assert json.load(open(os.path.join(d, 'prophist.json'))) == {'t': 50, 'p': {'77|pts': [[10, 12.5, '-123', '-103'], [30, 13.5, '-102', '-125']]}}


def test_empty_day():
    assert prop_hist.write(tempfile.mkdtemp()) is None
