#!/usr/bin/env python3
"""
Pre-registered test (Minutes Lab v2): should live pricing use minutes model v3 instead of v2?

Everything else stays v2 (v1 per-minute rates, the v2 adjustments); only the minutes change. Candidates, against the
shipped v2 on identical player-games and prices, each with its adjustments, spread and line calibration refit on
2024-25 exactly as every earlier candidate was:
  v2m3    minutes model v3 (role, returns from absence, new-team learning rate, market spread)
  v2m3s   minutes model v3 with NBA.com's confirmed starters in the role term and its inactive list added to Out
          (build_starters.py). Prices are Kalshi's 30-minute pre-tip VWAP and the last pre-tip book line, set after
          lineups are usually out, so this is fair to the feed.

Rule, fixed before this ran (build_prop_model_v3.choose): a candidate replaces v2's minutes only if every v2 GO
signal stays GO with out-of-sample ROI at least v2's; among those, the lowest average Kalshi log loss. Else v2 stays.

  python3 nba/scripts/build_minutes_v3_pricing.py
Writes data/minutes_v3_pricing.json and docs/minutes-v3-pricing.md.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model_v3_full as F
import build_starters as ST

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'minutes_v3_pricing.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-v3-pricing.md')
HEAD = ['# v2 pricing with minutes model v3: pre-registered test', '',
        'Generated {generated} by `nba/scripts/build_minutes_v3_pricing.py`. Fit on 2024-25, tested on 2025-26,',
        '{n_test:,} identical player-games and prices. Only the minutes change: v1 per-minute rates and the v2 adjustments',
        'everywhere, refit to each candidate\'s minutes.', '',
        '- **v2**: shipped (minutes model v2). **v2m3**: minutes model v3. **v2m3s**: minutes model v3 with NBA.com\'s',
        '  confirmed starters and inactive list.', '',
        'Rule (fixed before running): replace v2\'s minutes only if every v2 GO stays GO with ROI at least v2\'s; then',
        'the lowest Kalshi log loss.']
FOOT = ['Team minutes targets: v2m3 {team_min_m3}, v2m3s {team_min_m3s}. Related: [prop-model-v3-full.md](prop-model-v3-full.md),',
        '[starters-feed.md](starters-feed.md), [minutes-model-v3.md](minutes-model-v3.md).']


def main():
    I = F.inputs()
    feed, _ = ST.load_feed(I['box'])
    m3, tm3 = F.walk_v3(I, rates=False)
    m3s, tm3s = F.walk_v3(I, feed, rates=False)
    res = F.compare(F.walk_v2(I), {'v2m3': m3, 'v2m3s': m3s}, None)
    res.update(team_min_m3=tm3, team_min_m3s=tm3s)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    F.write_md(res, HEAD, FOOT, OUT_MD)
    print(open(OUT_MD).read())


if __name__ == '__main__':
    main()
