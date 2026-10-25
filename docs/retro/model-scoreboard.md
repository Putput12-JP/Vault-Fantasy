# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3822  LL 0.6995 vs 0.6869  skill -0.018 z -3.5    n=3519  LL 0.6993 vs 0.6860  skill -0.019 z -3.6    market better than Vault
pass_att      n= 130  LL 0.7070 vs 0.6885  skill -0.027 z -1.0    n= 133  LL 0.7077 vs 0.6947  skill -0.019 z -0.7    level with the market (within noise)
pass_cmp      n= 150  LL 0.7137 vs 0.6885  skill -0.037 z -1.7    n= 152  LL 0.7157 vs 0.6849  skill -0.045 z -2.0    level with the market (within noise)
pass_td       n= 185  LL 0.6476 vs 0.6695  skill +0.033 z +1.5    n= 188  LL 0.6587 vs 0.6789  skill +0.030 z +1.4    level with the market (within noise)
pass_yd       n= 156  LL 0.7261 vs 0.6938  skill -0.047 z -1.9    n= 156  LL 0.7247 vs 0.6932  skill -0.045 z -1.9    level with the market (within noise)
rec           n=1143  LL 0.6868 vs 0.6779  skill -0.013 z -1.4    n=1161  LL 0.6880 vs 0.6756  skill -0.018 z -2.0    level with the market (within noise)
rec_yd        n=1179  LL 0.7043 vs 0.6893  skill -0.022 z -2.3    n= 914  LL 0.7020 vs 0.6895  skill -0.018 z -1.9    market better than Vault
rush_att      n= 455  LL 0.7098 vs 0.6990  skill -0.015 z -1.0    n= 445  LL 0.6970 vs 0.6947  skill -0.003 z -0.2    level with the market (within noise)
rush_yd       n= 424  LL 0.7146 vs 0.6953  skill -0.028 z -1.4    n= 370  LL 0.7306 vs 0.6974  skill -0.048 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             426             51%        55%   +1.4
pass_int        196             49%        50%   +0.4
pass_td          33             64%        67%   +0.3
rec             149             55%        61%   +1.5
rec_yd           34             40%        41%   +0.2
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -87.4u         52%   -152.5u
pass_att              62%   +0.1pp        57%    +11.7u         56%     +9.7u
pass_cmp              60%   +0.2pp        47%    -19.2u         47%    -15.4u
pass_td               49%   -0.1pp        58%     +0.7u         58%     +2.0u
pass_yd               57%   +0.2pp        48%    -15.1u         48%    -15.0u
rec                   58%   +0.1pp        58%    +47.5u         55%    +24.6u
rec_yd                55%   -0.1pp        52%    -23.1u         51%    -41.9u
rush_att              62%   +0.6pp        53%     +0.4u         50%    -16.4u
rush_yd               57%   +0.0pp        46%    -46.7u         46%    -57.2u
```

## Game markets (at the close)

```
games   n= 273  LL 0.7075 vs 0.6890  skill -0.027 z -1.9    level with the market (within noise)     beat close   27%  units  -20.8u
ml      n=  81  LL 0.6778 vs 0.6784  skill +0.001 z +0.0    level with the market (within noise)     beat close   42%  units   +5.2u
spread  n=  94  LL 0.7163 vs 0.6945  skill -0.032 z -1.5    level with the market (within noise)     beat close   23%  units  -19.6u
total   n=  98  LL 0.7236 vs 0.6926  skill -0.045 z -1.8    level with the market (within noise)     beat close   19%  units   -6.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1466  47.7% vs  49.4%           n=1595  48.1% vs  49.5%
usage down                n= 461  51.0% vs  49.3%           n= 520  50.8% vs  48.9%
usage up / teammate out   n=2051  50.6% vs  49.5%           n=2180  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 615  Vault's side won 313-302  skill -0.062 z -3.2
  agrees with the news     n= 350  Vault's side won 187-163  skill -0.003 z -0.1
  no news                  n= 579  Vault's side won 304-275  skill -0.026 z -1.3
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 66  toward  39 / away  15  avg move toward +0.49 pts ±0.11
spread  FanDuel     n= 56  toward  30 / away  15  avg move toward +0.25 pts ±0.15
        -> NO-GO: not ahead of the control (+0.24 pts, z +1.3)
total   Pinnacle    n= 34  toward  21 / away  11  avg move toward +0.30 pts ±0.18
total   FanDuel     n= 37  toward  21 / away  11  avg move toward +0.08 pts ±0.16
        -> too few games (34 of 50)
props   Pinnacle    n=171  toward  83 / away  12  net share toward +0.41 ±0.07
props   FanDuel     n= 45  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.08, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 24  side won  14, price said   11.8  -> tracking (24 of 50)
  all Kalshi-priced lines: n=725  log-loss Kalshi 0.6862  books 0.6882
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=271  model lean won 132  overs hit 135  | would-be plays 6-9 -3.4u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     547       44-55 -9.8u     47-52 -7.0u         6-6 +0.7u       6-6 +1.2u
Wk 7     293       20-25 -3.5u     20-25 -4.7u         2-3 -0.6u       2-3 -0.4u
all     3047    343-325 +17.8u   338-330 -2.6u      54-45 +12.7u    55-44 +12.8u
log-loss at the open, same 3047 props: market 0.6850  live model 0.6957  anchored 0.6841
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           16-9         +6.8u           +5.4u       13/24
1-3 days before         14-13         +2.7u           +3.3u        4/26
6-24 hours before        9-10         -0.8u           -1.2u        5/17
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7236 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7178 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7661 vs 0.7216  skill -0.062 z -2.3
Wk  7  props n= 307  LL 0.6821 vs 0.6917  skill +0.014 z +0.9     games n=  23  LL 0.7166 vs 0.6694  skill -0.071 z -2.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
