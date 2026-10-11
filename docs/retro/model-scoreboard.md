# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2484  LL 0.7017 vs 0.6877  skill -0.020 z -3.0    n=2257  LL 0.7009 vs 0.6872  skill -0.020 z -2.8    market better than Vault
pass_att      n=  76  LL 0.7162 vs 0.6872  skill -0.042 z -1.3    n=  77  LL 0.7214 vs 0.6923  skill -0.042 z -1.1    level with the market (within noise)
pass_cmp      n=  94  LL 0.7163 vs 0.6884  skill -0.041 z -1.6    n=  94  LL 0.7163 vs 0.6783  skill -0.056 z -2.1    level with the market (within noise)
pass_td       n= 130  LL 0.6350 vs 0.6668  skill +0.048 z +2.1    n= 129  LL 0.6521 vs 0.6795  skill +0.040 z +1.8    Vault better than the market
pass_yd       n=  95  LL 0.7161 vs 0.6923  skill -0.035 z -1.4    n=  95  LL 0.7215 vs 0.6920  skill -0.043 z -1.7    level with the market (within noise)
rec           n= 766  LL 0.6877 vs 0.6779  skill -0.014 z -1.2    n= 763  LL 0.6882 vs 0.6773  skill -0.016 z -1.3    level with the market (within noise)
rec_yd        n= 788  LL 0.7073 vs 0.6908  skill -0.024 z -1.9    n= 599  LL 0.7054 vs 0.6912  skill -0.021 z -1.6    level with the market (within noise)
rush_att      n= 286  LL 0.7233 vs 0.7069  skill -0.023 z -1.2    n= 278  LL 0.7054 vs 0.7007  skill -0.007 z -0.3    level with the market (within noise)
rush_yd       n= 249  LL 0.7217 vs 0.6952  skill -0.038 z -1.4    n= 222  LL 0.7325 vs 0.6978  skill -0.050 z -1.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             285             51%        55%   +1.3
pass_int        135             49%        51%   +0.5
pass_td          25             64%        68%   +0.5
rec              92             55%        60%   +0.8
rec_yd           23             38%        44%   +0.5
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        52%    -79.5u         51%   -132.0u
pass_att              71%   +0.2pp        56%     +4.5u         56%     +4.6u
pass_cmp              60%   +0.2pp        44%    -18.1u         45%    -14.8u
pass_td               52%   +0.1pp        59%     +3.7u         59%     +3.0u
pass_yd               57%   -0.0pp        41%    -22.4u         42%    -20.9u
rec                   59%   +0.2pp        58%    +33.2u         54%     +5.5u
rec_yd                55%   -0.1pp        52%    -13.2u         52%    -20.3u
rush_att              62%   +0.6pp        52%     -3.3u         49%    -15.3u
rush_yd               58%   +0.1pp        47%    -24.7u         45%    -39.8u
```

## Game markets (at the close)

```
games   n= 183  LL 0.7010 vs 0.6860  skill -0.022 z -1.1    level with the market (within noise)     beat close   31%  units   +0.2u
ml      n=  54  LL 0.6551 vs 0.6689  skill +0.021 z +0.5    level with the market (within noise)     beat close   43%  units  +10.8u
spread  n=  63  LL 0.7056 vs 0.6933  skill -0.018 z -0.6    level with the market (within noise)     beat close   30%  units   -5.7u
total   n=  66  LL 0.7342 vs 0.6930  skill -0.059 z -1.9    level with the market (within noise)     beat close   23%  units   -4.9u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 100  48.0% vs  49.4%           n= 110  48.2% vs  49.8%
no news                   n= 951  47.7% vs  49.5%           n=1055  48.3% vs  49.7%
usage down                n= 309  51.1% vs  48.9%           n= 355  50.4% vs  48.7%
usage up / teammate out   n=1305  50.2% vs  49.5%           n=1396  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 398  Vault's side won 203-195  skill -0.067 z -2.6
  agrees with the news     n= 243  Vault's side won 129-114  skill +0.001 z +0.0
  no news                  n= 395  Vault's side won 209-186  skill -0.042 z -1.6
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 29  toward  19 / away   7  avg move toward +0.50 pts ±0.14
spread  FanDuel     n= 22  toward  14 / away   6  avg move toward +0.34 pts ±0.23
        -> too few games (29 of 50)
total   Pinnacle    n= 13  toward   9 / away   3  avg move toward +0.44 pts ±0.22
total   FanDuel     n= 13  toward   9 / away   2  avg move toward +0.19 pts ±0.19
        -> too few games (13 of 50)
props   Pinnacle    n= 61  toward  26 / away   6  net share toward +0.33 ±0.12
props   FanDuel     n= 18  toward   8 / away   3  net share toward +0.28 ±0.23
props   DraftKings  n= 17  toward   8 / away   1  net share toward +0.41 ±0.22
        -> too few props (61 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 11  side won   6, price said    5.1  -> tracking (11 of 50)
  all Kalshi-priced lines: n=163  log-loss Kalshi 0.6901  books 0.6912
Vault vs Kalshi (10+ pts, Kalshi)  n= 92  side won  41, price said   48.8  -> no edge yet (z -1.6)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=110  model lean won 56  overs hit 54  | would-be plays 2-4 -2.2u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     144       13-12 +0.2u     12-13 -2.4u         4-4 -0.4u       4-4 -0.5u
all     1785    235-200 +32.8u  227-208 +13.7u       36-32 +6.9u     37-31 +7.3u
log-loss at the open, same 1785 props: market 0.6857  live model 0.6952  anchored 0.6847
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-3         +4.8u           +4.0u        6/10
1-3 days before           9-9         +0.8u           +2.1u        1/17
6-24 hours before         7-6         +1.2u           +1.0u        3/11
under 6 hours           16-12         +2.5u           +0.1u        6/22
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 151  LL 0.6853 vs 0.6667  skill -0.028 z -1.2     games n=  12  LL 0.6901 vs 0.6960  skill +0.008 z +0.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
