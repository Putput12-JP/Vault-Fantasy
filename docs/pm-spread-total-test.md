# Sharp Polymarket accounts on spreads and totals: test plan

Written before the run. Question: does the Sharp Money "sharp net money" table deserve spread and total versions, or was moneyline the only market where account skill showed up?

## Data
- Settled NFL, CFB and NBA games from the same Polymarket series the moneyline scorecard uses (`scripts/build_pm_wallets.py`).
- Per game: the highest-volume spread market and the highest-volume total market (the main line), plus the moneyline as a control.
- Unit, identical to the scorecard: $1k+ taker trades before kickoff. Score per trade = closing price of the side bought / price paid - 1. Close = last trade before kickoff.

## Tests
1. **Transfer.** Accounts the moneyline scorecard calls sharp (t >= 2, 10+ trades, 5+ games) and dull (t <= -2): their CLV on spread and total trades. Control: the same accounts on moneyline trades in the same games.
2. **Own-market skill.** Order games by kickoff and split in half. Label accounts sharp on the first half of that market alone (same rule: t >= 2, 10+ trades, 5+ games). Measure their CLV on the second half.
3. **Depth.** Average number of $1k+ pre-kickoff taker trades per game, spread and total vs moneyline.

## Rule
GO for a spread or total version of the table only if test 1 or test 2 gives a mean CLV above zero by 2+ standard errors on 100+ trades for that market. Otherwise NO-GO and the table stays moneyline-only.

Even a GO is context, not a bet to copy: the moneyline result was that the price has priced these accounts in by kickoff.

## Known limit
The sharp/dull labels come from moneyline results in the same games, so test 1 is not fully out-of-sample. Test 2 is the clean one.
