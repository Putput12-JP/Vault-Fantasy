"""build_game_ctx.py: both teams' rows per game, spreads from each team's side, stored lines only, past seasons kept without raw/."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import build_game_ctx as G

PICKS = {'cols': ['game', 'clock', 'margin', 'total', 'p_home', 'book', 'spread'],
         'days': {'2026-10-20': {'games': {'1': ['PHI @ NY', 0, 'PHI', 'NY', 106.0, 100.0],      # NY home -4.5, lost by 6
                                           '2': ['BOS @ DET', 0, 'BOS', 'DET', None, None]},      # not final: skipped
                                 'rows': [['1', 'f', 0, 0, 0, 'DraftKings', -3.5], ['1', 'c', 0, 0, 0, 'DraftKings', -4.5]]}}}
DAY = '20746'                                                      # 2026-10-20 as days since 1970


def setup(tmp, lines=None, old=None):
    G.DATA, G.OUT, G.LINES = tmp, os.path.join(tmp, 'game_ctx.json'), os.path.join(tmp, 'game_lines.csv')
    json.dump(PICKS, open(os.path.join(tmp, 'game_picks.json'), 'w'))
    json.dump({'players': {'9': [[DAY, 2026]]}}, open(os.path.join(tmp, 'gamelogs.json'), 'w'))
    if lines:
        open(G.LINES, 'w').write(lines)
    if old:
        json.dump(old, open(G.OUT, 'w'))


def test_current_season_close_spread_both_sides():
    tmp = tempfile.mkdtemp(); setup(tmp)
    g, np, nc = G.build()
    assert np is None and nc == 1
    assert g['NY'][DAY] == [100, 106, -4.5]                        # the close row, not the first
    assert g['PHI'][DAY] == [106, 100, 4.5]
    assert 'DET' not in g


def test_past_seasons_kept_without_raw():
    tmp = tempfile.mkdtemp(); setup(tmp, old={'g': {'LAL': {'20000': [110, 100, -6.0]}, 'NY': {DAY: [1, 2, None]}}})
    g, _, _ = G.build()
    assert g['LAL']['20000'] == [110, 100, -6.0]                   # before this season: carried over
    assert g['NY'][DAY] == [100, 106, -4.5]                        # this season: rebuilt, never carried


def test_past_from_lines_csv_prefers_draftkings_and_keeps_missing_spread_null():
    hdr = 'game_id,season,tip,type,home,away,home_score,away_score,book,spread_open,spread_close\n'
    rows = ('7,2026,2026-03-01T00:30Z,STD,LAL,GS,110,100,ESPN BET,-5,-5.5\n'
            '7,2026,2026-03-01T00:30Z,STD,LAL,GS,110,100,DraftKings,-6,-6.5\n'
            '8,2026,2026-03-02T00:30Z,STD,MIA,ORL,99,101,DraftKings,,\n'
            '9,2024,2024-03-02T00:30Z,STD,MIA,ORL,99,101,DraftKings,-2,-2\n')    # before the game logs: dropped
    tmp = tempfile.mkdtemp(); setup(tmp, lines=hdr + rows)
    g, np, _ = G.build()
    assert np == 2
    d = str(G.dnum('2026-02-28'))                                  # 00:30Z on Mar 1 is the evening of Feb 28 in New York
    assert g['LAL'][d] == [110, 100, -6.5] and g['GS'][d] == [100, 110, 6.5]
    assert g['ORL'][str(G.dnum('2026-03-01'))] == [101, 99, None]
