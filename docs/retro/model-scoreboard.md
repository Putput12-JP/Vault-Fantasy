# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4150  LL 0.6994 vs 0.6858  skill -0.020 z -3.9    n=3811  LL 0.6992 vs 0.6851  skill -0.021 z -4.0    market better than Vault
pass_att      n= 143  LL 0.7107 vs 0.6880  skill -0.033 z -1.3    n= 146  LL 0.7120 vs 0.6952  skill -0.024 z -0.9    level with the market (within noise)
pass_cmp      n= 163  LL 0.7161 vs 0.6877  skill -0.041 z -2.0    n= 164  LL 0.7189 vs 0.6840  skill -0.051 z -2.3    level with the market (within noise)
pass_td       n= 199  LL 0.6453 vs 0.6632  skill +0.027 z +1.3    n= 202  LL 0.6567 vs 0.6721  skill +0.023 z +1.1    level with the market (within noise)
pass_yd       n= 169  LL 0.7275 vs 0.6929  skill -0.050 z -2.1    n= 168  LL 0.7271 vs 0.6933  skill -0.049 z -2.1    market better than Vault
rec           n=1242  LL 0.6861 vs 0.6770  skill -0.013 z -1.5    n=1262  LL 0.6876 vs 0.6761  skill -0.017 z -1.9    level with the market (within noise)
rec_yd        n=1281  LL 0.7032 vs 0.6884  skill -0.021 z -2.5    n= 997  LL 0.7018 vs 0.6886  skill -0.019 z -2.1    market better than Vault
rush_att      n= 493  LL 0.7076 vs 0.6986  skill -0.013 z -0.9    n= 480  LL 0.6955 vs 0.6918  skill -0.005 z -0.4    level with the market (within noise)
rush_yd       n= 460  LL 0.7199 vs 0.6943  skill -0.037 z -1.9    n= 392  LL 0.7317 vs 0.6971  skill -0.050 z -2.4    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             469             51%        53%   +0.8
pass_int        210             49%        50%   +0.4
pass_td          34             64%        65%   +0.1
rec             169             55%        59%   +1.0
rec_yd           39             40%        36%   -0.5
rush_yd          16             45%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -93.4u         52%   -165.1u
pass_att              63%   +0.2pp        56%    +10.4u         55%     +8.0u
pass_cmp              59%   +0.2pp        46%    -22.8u         47%    -17.2u
pass_td               50%   -0.0pp        60%     +4.9u         59%     +4.7u
pass_yd               57%   +0.1pp        49%    -13.4u         49%    -15.0u
rec                   59%   +0.2pp        58%    +51.0u         55%    +29.6u
rec_yd                56%   -0.1pp        51%    -34.3u         51%    -58.4u
rush_att              63%   +0.7pp        53%     +2.3u         50%    -14.8u
rush_yd               57%   +0.0pp        45%    -57.5u         45%    -66.2u
```

## Game markets (at the close)

```
games   n= 294  LL 0.7054 vs 0.6875  skill -0.026 z -1.9    level with the market (within noise)     beat close   28%  units  -13.7u
ml      n=  88  LL 0.6718 vs 0.6725  skill +0.001 z +0.0    level with the market (within noise)     beat close   43%  units   +9.0u
spread  n= 101  LL 0.7144 vs 0.6956  skill -0.027 z -1.4    level with the market (within noise)     beat close   23%  units  -18.9u
total   n= 105  LL 0.7249 vs 0.6921  skill -0.047 z -1.8    level with the market (within noise)     beat close   20%  units   -3.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 192  48.4% vs  49.4%           n= 216  47.7% vs  49.2%
no news                   n=1512  48.0% vs  49.3%           n=1659  48.0% vs  49.5%
usage down                n= 483  50.3% vs  49.2%           n= 550  50.0% vs  48.9%
usage up / teammate out   n=2294  50.1% vs  49.5%           n=2437  49.2% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 685  Vault's side won 349-336  skill -0.061 z -3.3
  agrees with the news     n= 386  Vault's side won 208-178  skill -0.001 z -0.1
  no news                  n= 585  Vault's side won 304-281  skill -0.034 z -1.7
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 70  toward  42 / away  15  avg move toward +0.48 pts ±0.11
spread  FanDuel     n= 60  toward  33 / away  16  avg move toward +0.29 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 35  toward  22 / away  11  avg move toward +0.31 pts ±0.17
total   FanDuel     n= 38  toward  21 / away  12  avg move toward +0.05 pts ±0.15
        -> too few games (35 of 50)
props   Pinnacle    n=212  toward 108 / away  17  net share toward +0.43 ±0.06
props   FanDuel     n= 65  toward  33 / away   9  net share toward +0.37 ±0.12
props   DraftKings  n= 28  toward  10 / away   4  net share toward +0.21 ±0.18
        -> NO-GO: not ahead of the controls (+0.06, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 31  side won  19, price said   15.2  -> tracking (31 of 50)
  all Kalshi-priced lines: n=861  log-loss Kalshi 0.6847  books 0.6878
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=334  model lean won 171  overs hit 167  | would-be plays 6-10 -4.4u
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
Wk 7     541       40-40 +1.4u     41-39 +1.6u         3-6 -2.5u       3-6 -2.4u
Wk 8      44         1-5 -4.1u       1-5 -4.1u         1-1 -0.1u       1-1 -0.1u
all     3339    364-345 +18.6u   360-349 -0.5u      56-49 +10.6u    57-48 +10.6u
log-loss at the open, same 3339 props: market 0.6841  live model 0.6960  anchored 0.6835
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           16-9         +6.8u           +5.4u       13/24
1-3 days before         16-13         +4.4u           +4.8u        5/28
6-24 hours before       10-12         -2.2u           -2.7u        7/20
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7230 vs 0.6807  skill -0.062 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7172 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6658 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7011 vs 0.6903  skill -0.016 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7655 vs 0.7216  skill -0.061 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7059 vs 0.6723  skill -0.050 z -1.2
Wk  8  props n=  48  LL 0.7290 vs 0.6642  skill -0.098 z -2.5     games n=   3  LL 0.6134 vs 0.6150  skill +0.003 z +0.0
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
