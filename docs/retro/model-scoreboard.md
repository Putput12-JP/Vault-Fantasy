# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4187  LL 0.6984 vs 0.6857  skill -0.019 z -3.7    n=3843  LL 0.6984 vs 0.6851  skill -0.019 z -3.8    market better than Vault
pass_att      n= 145  LL 0.7082 vs 0.6881  skill -0.029 z -1.1    n= 148  LL 0.7097 vs 0.6954  skill -0.021 z -0.8    level with the market (within noise)
pass_cmp      n= 165  LL 0.7138 vs 0.6881  skill -0.037 z -1.8    n= 166  LL 0.7166 vs 0.6846  skill -0.047 z -2.1    level with the market (within noise)
pass_td       n= 200  LL 0.6443 vs 0.6623  skill +0.027 z +1.3    n= 204  LL 0.6549 vs 0.6709  skill +0.024 z +1.2    level with the market (within noise)
pass_yd       n= 171  LL 0.7247 vs 0.6928  skill -0.046 z -2.0    n= 170  LL 0.7245 vs 0.6933  skill -0.045 z -1.9    level with the market (within noise)
rec           n=1251  LL 0.6852 vs 0.6767  skill -0.012 z -1.4    n=1271  LL 0.6871 vs 0.6761  skill -0.016 z -1.9    level with the market (within noise)
rec_yd        n=1290  LL 0.7027 vs 0.6887  skill -0.020 z -2.4    n=1003  LL 0.7014 vs 0.6885  skill -0.019 z -2.1    market better than Vault
rush_att      n= 499  LL 0.7062 vs 0.6978  skill -0.012 z -0.8    n= 486  LL 0.6952 vs 0.6921  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 466  LL 0.7188 vs 0.6943  skill -0.035 z -1.9    n= 395  LL 0.7305 vs 0.6970  skill -0.048 z -2.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             474             51%        53%   +0.9
pass_int        212             49%        50%   +0.4
pass_td          34             64%        65%   +0.1
rec             171             55%        59%   +1.2
rec_yd           40             40%        38%   -0.3
rush_yd          16             45%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -82.7u         52%   -161.2u
pass_att              64%   +0.2pp        56%    +10.2u         55%     +8.0u
pass_cmp              60%   +0.2pp        46%    -22.8u         47%    -17.2u
pass_td               50%   -0.0pp        60%     +6.2u         60%     +6.2u
pass_yd               57%   +0.1pp        50%    -11.7u         49%    -13.3u
rec                   59%   +0.2pp        58%    +52.3u         55%    +29.6u
rec_yd                56%   -0.1pp        52%    -34.1u         51%    -59.8u
rush_att              63%   +0.7pp        54%     +8.0u         51%    -11.7u
rush_yd               58%   +0.0pp        45%    -56.9u         45%    -66.8u
```

## Game markets (at the close)

```
games   n= 296  LL 0.7063 vs 0.6875  skill -0.027 z -1.9    level with the market (within noise)     beat close   28%  units  -15.7u
ml      n=  88  LL 0.6718 vs 0.6725  skill +0.001 z +0.0    level with the market (within noise)     beat close   43%  units   +9.0u
spread  n= 102  LL 0.7148 vs 0.6955  skill -0.028 z -1.4    level with the market (within noise)     beat close   24%  units  -19.9u
total   n= 106  LL 0.7268 vs 0.6922  skill -0.050 z -1.9    level with the market (within noise)     beat close   20%  units   -4.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 192  48.4% vs  49.4%           n= 216  47.7% vs  49.2%
no news                   n=1534  47.9% vs  49.4%           n=1684  47.9% vs  49.5%
usage down                n= 491  49.7% vs  49.2%           n= 559  49.4% vs  48.9%
usage up / teammate out   n=2302  50.1% vs  49.5%           n=2446  49.2% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 685  Vault's side won 349-336  skill -0.061 z -3.3
  agrees with the news     n= 389  Vault's side won 211-178  skill +0.001 z +0.1
  no news                  n= 593  Vault's side won 312-281  skill -0.029 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 75  toward  46 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 65  toward  37 / away  17  avg move toward +0.28 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 39  toward  24 / away  12  avg move toward +0.23 pts ±0.17
total   FanDuel     n= 40  toward  23 / away  12  avg move toward +0.15 pts ±0.17
        -> too few games (39 of 50)
props   Pinnacle    n=230  toward 120 / away  20  net share toward +0.43 ±0.06
props   FanDuel     n= 68  toward  41 / away   9  net share toward +0.47 ±0.11
props   DraftKings  n= 28  toward  10 / away   4  net share toward +0.21 ±0.18
        -> NO-GO: not ahead of the controls (-0.04, z -0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 31  side won  19, price said   15.2  -> tracking (31 of 50)
  all Kalshi-priced lines: n=871  log-loss Kalshi 0.684  books 0.687
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=341  model lean won 172  overs hit 167  | would-be plays 6-10 -4.4u
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
Wk 8      76         2-5 -3.3u       2-5 -3.3u         1-1 -0.1u       1-1 -0.1u
all     3371    365-345 +19.4u   361-349 +0.3u      56-49 +10.6u    57-48 +10.6u
log-loss at the open, same 3371 props: market 0.6840  live model 0.6951  anchored 0.6832
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           17-9         +7.7u           +6.3u       14/25
1-3 days before         16-13         +4.4u           +4.8u        5/28
6-24 hours before       10-12         -2.2u           -2.7u        7/20
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7235 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7177 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7010 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7660 vs 0.7216  skill -0.062 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7061 vs 0.6723  skill -0.050 z -1.2
Wk  8  props n=  85  LL 0.6660 vs 0.6678  skill +0.003 z +0.1     games n=   5  LL 0.6934 vs 0.6453  skill -0.074 z -1.0
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
