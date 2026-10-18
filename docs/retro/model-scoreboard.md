# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3014  LL 0.7000 vs 0.6872  skill -0.019 z -3.1    n=2760  LL 0.6997 vs 0.6868  skill -0.019 z -3.0    market better than Vault
pass_att      n=  96  LL 0.7114 vs 0.6879  skill -0.034 z -1.2    n=  97  LL 0.7116 vs 0.6904  skill -0.031 z -1.0    level with the market (within noise)
pass_cmp      n= 114  LL 0.7185 vs 0.6895  skill -0.042 z -1.8    n= 115  LL 0.7188 vs 0.6811  skill -0.055 z -2.2    level with the market (within noise)
pass_td       n= 152  LL 0.6435 vs 0.6689  skill +0.038 z +1.7    n= 153  LL 0.6580 vs 0.6819  skill +0.035 z +1.6    level with the market (within noise)
pass_yd       n= 120  LL 0.7286 vs 0.6934  skill -0.051 z -2.0    n= 120  LL 0.7319 vs 0.6920  skill -0.058 z -2.3    market better than Vault
rec           n= 919  LL 0.6891 vs 0.6799  skill -0.013 z -1.2    n= 921  LL 0.6897 vs 0.6781  skill -0.017 z -1.6    level with the market (within noise)
rec_yd        n= 942  LL 0.7032 vs 0.6892  skill -0.020 z -1.9    n= 723  LL 0.7005 vs 0.6898  skill -0.016 z -1.4    level with the market (within noise)
rush_att      n= 350  LL 0.7160 vs 0.7012  skill -0.021 z -1.2    n= 344  LL 0.7028 vs 0.6957  skill -0.010 z -0.6    level with the market (within noise)
rush_yd       n= 321  LL 0.7102 vs 0.6922  skill -0.026 z -1.1    n= 287  LL 0.7231 vs 0.6979  skill -0.036 z -1.5    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             341             51%        55%   +1.4
pass_int        160             49%        49%   +0.1
pass_td          26             64%        69%   +0.6
rec             115             55%        62%   +1.4
rec_yd           28             39%        46%   +0.8
rush_yd          12             45%        58%   +0.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -82.9u         51%   -130.5u
pass_att              63%   +0.0pp        59%    +10.9u         59%    +11.4u
pass_cmp              60%   +0.2pp        43%    -22.1u         44%    -18.5u
pass_td               51%   +0.1pp        60%     +6.0u         60%     +5.8u
pass_yd               57%   +0.2pp        42%    -25.2u         43%    -23.8u
rec                   58%   +0.1pp        58%    +30.9u         54%     +6.5u
rec_yd                57%   -0.1pp        53%     +0.3u         53%     -6.5u
rush_att              62%   +0.6pp        51%     -8.5u         49%    -21.1u
rush_yd               55%   +0.1pp        47%    -28.4u         46%    -41.9u
```

## Game markets (at the close)

```
games   n= 219  LL 0.6998 vs 0.6872  skill -0.018 z -1.1    level with the market (within noise)     beat close   29%  units   -4.3u
ml      n=  65  LL 0.6642 vs 0.6740  skill +0.015 z +0.4    level with the market (within noise)     beat close   42%  units   +8.4u
spread  n=  75  LL 0.7065 vs 0.6931  skill -0.019 z -0.7    level with the market (within noise)     beat close   27%  units   -8.2u
total   n=  79  LL 0.7227 vs 0.6926  skill -0.043 z -1.6    level with the market (within noise)     beat close   20%  units   -4.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 129  48.8% vs  49.5%           n= 142  48.6% vs  49.4%
no news                   n=1122  49.2% vs  49.4%           n=1234  49.3% vs  49.6%
usage down                n= 363  51.0% vs  49.2%           n= 417  50.6% vs  48.9%
usage up / teammate out   n=1640  50.0% vs  49.5%           n=1745  49.1% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 488  Vault's side won 253-235  skill -0.060 z -2.7
  agrees with the news     n= 285  Vault's side won 153-132  skill +0.000 z +0.0
  no news                  n= 450  Vault's side won 236-214  skill -0.039 z -1.6
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 54  toward  32 / away  13  avg move toward +0.48 pts ±0.12
spread  FanDuel     n= 44  toward  23 / away  12  avg move toward +0.16 pts ±0.16
        -> NO-GO: not ahead of the control (+0.32 pts, z +1.6)
total   Pinnacle    n= 26  toward  19 / away   6  avg move toward +0.42 pts ±0.21
total   FanDuel     n= 33  toward  19 / away   9  avg move toward +0.13 pts ±0.16
        -> too few games (26 of 50)
props   Pinnacle    n=128  toward  65 / away  10  net share toward +0.43 ±0.08
props   FanDuel     n= 35  toward  16 / away   7  net share toward +0.26 ±0.16
props   DraftKings  n= 23  toward  10 / away   3  net share toward +0.30 ±0.20
        -> NO-GO: not ahead of the controls (+0.13, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=394  log-loss Kalshi 0.6858  books 0.688
Vault vs Kalshi (10+ pts, Kalshi)  n=162  side won  72, price said   85.9  -> no edge yet (z -2.2)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=166  model lean won 91  overs hit 88  | would-be plays 5-8 -3.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6      81         9-2 +7.3u       9-2 +6.3u         1-1 -0.3u       1-1 -0.3u
all     2288    288-247 +38.3u  280-255 +15.4u      47-37 +12.2u    48-36 +11.7u
log-loss at the open, same 2288 props: market 0.6856  live model 0.6950  anchored 0.6846
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          12-9         +4.8u           +5.6u        2/20
6-24 hours before        8-10         -1.9u           -2.1u        4/16
under 6 hours           21-13         +6.3u           +2.6u        6/27
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7250 vs 0.6807  skill -0.065 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7192 vs 0.6851  skill -0.050 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7005 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n=  84  LL 0.6624 vs 0.6901  skill +0.040 z +1.6     games n=   6  LL 0.8082 vs 0.7496  skill -0.078 z -2.0
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
