# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4524  LL 0.6995 vs 0.6864  skill -0.019 z -4.0    n=4150  LL 0.6985 vs 0.6858  skill -0.018 z -3.8    market better than Vault
pass_att      n= 161  LL 0.7052 vs 0.6896  skill -0.023 z -0.9    n= 164  LL 0.7069 vs 0.6953  skill -0.017 z -0.7    level with the market (within noise)
pass_cmp      n= 180  LL 0.7089 vs 0.6884  skill -0.030 z -1.5    n= 181  LL 0.7101 vs 0.6852  skill -0.036 z -1.8    level with the market (within noise)
pass_td       n= 216  LL 0.6509 vs 0.6643  skill +0.020 z +1.0    n= 219  LL 0.6635 vs 0.6761  skill +0.019 z +1.0    level with the market (within noise)
pass_yd       n= 187  LL 0.7225 vs 0.6915  skill -0.045 z -2.0    n= 186  LL 0.7222 vs 0.6933  skill -0.042 z -1.9    market better than Vault
rec           n=1342  LL 0.6885 vs 0.6781  skill -0.015 z -1.8    n=1366  LL 0.6887 vs 0.6767  skill -0.018 z -2.1    level with the market (within noise)
rec_yd        n=1385  LL 0.7040 vs 0.6898  skill -0.021 z -2.5    n=1072  LL 0.7012 vs 0.6894  skill -0.017 z -2.0    market better than Vault
rush_att      n= 543  LL 0.7048 vs 0.6955  skill -0.013 z -1.0    n= 527  LL 0.6953 vs 0.6919  skill -0.005 z -0.4    level with the market (within noise)
rush_yd       n= 510  LL 0.7178 vs 0.6949  skill -0.033 z -1.8    n= 435  LL 0.7261 vs 0.6968  skill -0.042 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             504             51%        54%   +1.3
pass_int        228             49%        51%   +0.7
pass_td          37             64%        65%   +0.1
rec             178             55%        60%   +1.3
rec_yd           41             40%        39%   -0.1
rush_yd          18             46%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.1pp        53%    -89.5u         52%   -164.2u
pass_att              61%   +0.1pp        57%    +13.3u         56%    +11.5u
pass_cmp              60%   +0.2pp        45%    -27.4u         46%    -21.8u
pass_td               51%   +0.0pp        59%     +2.8u         58%     +2.3u
pass_yd               57%   +0.1pp        50%    -13.0u         49%    -14.2u
rec                   60%   +0.2pp        58%    +48.5u         55%    +32.0u
rec_yd                56%   -0.2pp        52%    -22.7u         51%    -52.1u
rush_att              63%   +0.6pp        53%     +1.2u         50%    -21.7u
rush_yd               58%   +0.1pp        46%    -61.2u         46%    -70.7u
```

## Game markets (at the close)

```
games   n= 318  LL 0.6996 vs 0.6832  skill -0.024 z -1.8    level with the market (within noise)     beat close   27%  units  -11.6u
ml      n=  94  LL 0.6574 vs 0.6570  skill -0.001 z -0.0    level with the market (within noise)     beat close   41%  units   +8.2u
spread  n= 110  LL 0.7124 vs 0.6958  skill -0.024 z -1.3    level with the market (within noise)     beat close   23%  units  -18.4u
total   n= 114  LL 0.7221 vs 0.6926  skill -0.043 z -1.8    level with the market (within noise)     beat close   19%  units   -1.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 194  47.9% vs  49.3%           n= 220  46.8% vs  49.2%
no news                   n=1759  48.3% vs  49.3%           n=1926  48.2% vs  49.5%
usage down                n= 543  49.5% vs  49.2%           n= 617  49.3% vs  48.8%
usage up / teammate out   n=2372  50.1% vs  49.4%           n=2527  49.3% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 714  Vault's side won 361-353  skill -0.065 z -3.6
  agrees with the news     n= 398  Vault's side won 214-184  skill +0.001 z +0.1
  no news                  n= 654  Vault's side won 341-313  skill -0.031 z -1.6
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 76  toward  47 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 66  toward  38 / away  17  avg move toward +0.28 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 39  toward  24 / away  12  avg move toward +0.23 pts ±0.17
total   FanDuel     n= 42  toward  24 / away  13  avg move toward +0.16 pts ±0.16
        -> too few games (39 of 50)
props   Pinnacle    n=230  toward 121 / away  20  net share toward +0.44 ±0.06
props   FanDuel     n= 68  toward  41 / away   9  net share toward +0.47 ±0.11
props   DraftKings  n= 28  toward  10 / away   4  net share toward +0.21 ±0.18
        -> NO-GO: not ahead of the controls (-0.03, z -0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 36  side won  24, price said   17.8  -> tracking (36 of 50)
  all Kalshi-priced lines: n=1007  log-loss Kalshi 0.6829  books 0.6859
Vault vs Kalshi (10+ pts, Kalshi)  n=167  side won  77, price said   88.8  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=360  model lean won 182  overs hit 176  | would-be plays 6-10 -4.4u
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
Wk 8     383       28-30 +0.0u     29-29 -0.7u         3-6 -2.4u       3-6 -2.7u
all     3678    391-370 +22.7u   388-373 +2.9u       58-54 +8.3u     59-53 +8.1u
log-loss at the open, same 3678 props: market 0.6850  live model 0.6955  anchored 0.6842
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          17-10         +6.7u           +5.3u       15/26
1-3 days before         17-14         +4.5u           +4.7u        7/30
6-24 hours before       11-12         -1.1u           -1.8u        8/21
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
Wk  8  props n= 422  LL 0.7038 vs 0.6893  skill -0.021 z -1.6     games n=  27  LL 0.6251 vs 0.6289  skill +0.006 z +0.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
