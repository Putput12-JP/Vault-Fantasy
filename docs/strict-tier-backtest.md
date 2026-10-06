```
STRICT TIER BACKTEST: 12320 real lines, 2024-25 ESPN BET close, QB volume markets excluded
price band -250..200

1) Shipped thresholds (model >= 0.70, market >= 0.58):
   2024: 73.5% hit (±4.8) | market 61.3% | ROI +12.6% | n=83 | 5.2 plays/week
   2025: 66.7% hit (±6.1) | market 61.7% | ROI  +1.3% | n=60 | 4.6 plays/week
   both: 70.6% hit (±3.8) | market 61.5% | ROI  +7.9% | n=143 | 4.9 plays/week

2) Walk-forward: best thresholds on ONE season (hit>=65%, n>=60, max ROI), scored once on the OTHER:
   fit 2024 -> model>=0.75 mkt>=0.52: in-sample 72.2% hit (±5.3) | market 57.7% | ROI +18.0% | n=72
      scored on 2025: 57.1% hit (±7.6) | market 59.4% | ROI  -9.8% | n=42
   fit 2025 -> model>=0.70 mkt>=0.58: in-sample 66.7% hit (±6.1) | market 61.7% | ROI  +1.3% | n=60
      scored on 2024: 73.5% hit (±4.8) | market 61.3% | ROI +12.6% | n=83

3) Sensitivity (both seasons):
   model>=0.60 mkt>=0.52: 58.2% hit (±1.2) | market 55.9% | ROI  -2.3% | n=1723
   model>=0.60 mkt>=0.55: 61.2% hit (±1.6) | market 58.5% | ROI  -1.7% | n=909
   model>=0.60 mkt>=0.58: 64.9% hit (±2.2) | market 60.7% | ROI  +0.4% | n=490
   model>=0.60 mkt>=0.60: 65.7% hit (±2.9) | market 62.3% | ROI  -1.2% | n=274
   model>=0.65 mkt>=0.52: 62.0% hit (±1.7) | market 56.6% | ROI  +3.2% | n=785
   model>=0.65 mkt>=0.55: 64.4% hit (±2.2) | market 59.2% | ROI  +2.4% | n=455
   model>=0.65 mkt>=0.58: 66.7% hit (±2.8) | market 61.2% | ROI  +2.3% | n=282
   model>=0.65 mkt>=0.60: 65.6% hit (±3.5) | market 62.5% | ROI  -1.9% | n=183
   model>=0.70 mkt>=0.52: 64.3% hit (±2.6) | market 57.0% | ROI  +6.0% | n=345
   model>=0.70 mkt>=0.55: 67.6% hit (±3.3) | market 59.8% | ROI  +6.3% | n=204
   model>=0.70 mkt>=0.58: 70.6% hit (±3.8) | market 61.5% | ROI  +7.9% | n=143
   model>=0.70 mkt>=0.60: 71.6% hit (±4.6) | market 62.9% | ROI  +6.7% | n=95
   model>=0.75 mkt>=0.52: 66.7% hit (±4.4) | market 58.3% | ROI  +7.8% | n=114
   model>=0.75 mkt>=0.55: 69.6% hit (±5.2) | market 60.7% | ROI  +8.5% | n=79
   model>=0.75 mkt>=0.58: 68.9% hit (±5.9) | market 62.1% | ROI  +4.5% | n=61
   model>=0.75 mkt>=0.60: 64.6% hit (±6.9) | market 63.0% | ROI  -3.8% | n=48

4) GAP tier (rush yds / rush att / rec yds where Vault's P(side) beats the market's by >= 0.15):
   2024: 55.6% hit (±2.0) | market 48.4% | ROI  +6.9% | n=590 | edge vs price +7.2 pts
   2025: 51.8% hit (±2.1) | market 49.1% | ROI  -1.5% | n=570 | edge vs price +2.6 pts
   both: 53.7% hit (±1.5) | market 48.8% | ROI  +2.8% | n=1160 | edge vs price +4.9 pts

By market at the shipped thresholds:
   pass_td   70.6% hit (±6.4) | market 63.0% | ROI  +5.3% | n=51
   rec       68.7% hit (±5.1) | market 60.6% | ROI  +6.2% | n=83
   rec_yd    66.7% hit (±27.2) | market 60.9% | ROI  +4.8% | n=3
   rush_att  100.0% hit (±0.0) | market 62.0% | ROI +51.9% | n=4
   rush_yd   100.0% hit (±0.0) | market 58.9% | ROI +60.7% | n=2

Caveats: one book's closing line (live uses the median of real books at the posted price); the replay
omits matchup/role/script multipliers the live board adds; the shipped thresholds were first found on this
same data, so the walk-forward in (2) is the honest number. Judge tiers on edge vs price (hit minus the
market's implied probability): chalk hits often at a price that already says so. Live shadow tracking is the real test.
```
