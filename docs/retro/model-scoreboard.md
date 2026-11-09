# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=5239  LL 0.7009 vs 0.6857  skill -0.022 z -5.0    n=4783  LL 0.7002 vs 0.6857  skill -0.021 z -4.7    market better than Vault
pass_att      n= 194  LL 0.7062 vs 0.6893  skill -0.024 z -1.2    n= 197  LL 0.7094 vs 0.6944  skill -0.022 z -1.0    level with the market (within noise)
pass_cmp      n= 210  LL 0.7089 vs 0.6870  skill -0.032 z -1.8    n= 209  LL 0.7130 vs 0.6857  skill -0.040 z -2.1    level with the market (within noise)
pass_td       n= 249  LL 0.6616 vs 0.6688  skill +0.011 z +0.6    n= 251  LL 0.6717 vs 0.6788  skill +0.011 z +0.6    level with the market (within noise)
pass_yd       n= 219  LL 0.7374 vs 0.6908  skill -0.068 z -3.4    n= 218  LL 0.7367 vs 0.6927  skill -0.064 z -3.2    market better than Vault
rec           n=1543  LL 0.6871 vs 0.6747  skill -0.018 z -2.4    n=1569  LL 0.6904 vs 0.6765  skill -0.021 z -2.7    market better than Vault
rec_yd        n=1587  LL 0.7035 vs 0.6906  skill -0.019 z -2.5    n=1224  LL 0.7014 vs 0.6903  skill -0.016 z -2.0    market better than Vault
rush_att      n= 636  LL 0.7062 vs 0.6948  skill -0.016 z -1.3    n= 613  LL 0.6948 vs 0.6890  skill -0.008 z -0.7    level with the market (within noise)
rush_yd       n= 601  LL 0.7219 vs 0.6952  skill -0.038 z -2.3    n= 502  LL 0.7243 vs 0.6968  skill -0.039 z -2.2    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             575             51%        55%   +1.6
pass_int        261             49%        51%   +0.6
pass_td          42             64%        62%   -0.3
rec             203             55%        61%   +1.8
rec_yd           45             40%        44%   +0.6
rush_yd          22             45%        46%   +0.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -166.7u         51%   -247.5u
pass_att              65%   +0.2pp        54%     +6.9u         54%     +5.1u
pass_cmp              61%   +0.2pp        46%    -27.0u         47%    -22.6u
pass_td               48%   -0.1pp        58%     -2.9u         57%     -4.3u
pass_yd               56%   +0.1pp        46%    -31.9u         45%    -32.9u
rec                   59%   +0.1pp        57%    +18.0u         54%     +6.0u
rec_yd                55%   -0.1pp        52%    -39.4u         51%    -65.8u
rush_att              62%   +0.6pp        53%     -2.3u         50%    -30.8u
rush_yd               60%   +0.1pp        47%    -56.3u         47%    -69.7u
```

## Game markets (at the close)

```
games   n= 365  LL 0.6965 vs 0.6772  skill -0.029 z -2.3    market better than Vault                 beat close   29%  units  -20.4u
ml      n= 107  LL 0.6450 vs 0.6382  skill -0.011 z -0.4    level with the market (within noise)     beat close   45%  units   +2.8u
spread  n= 127  LL 0.7138 vs 0.6945  skill -0.028 z -1.6    level with the market (within noise)     beat close   25%  units  -18.2u
total   n= 131  LL 0.7219 vs 0.6924  skill -0.043 z -1.9    level with the market (within noise)     beat close   20%  units   -5.0u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 237  46.4% vs  49.3%           n= 272  45.2% vs  49.3%
no news                   n=2016  48.3% vs  49.3%           n=2222  48.6% vs  49.4%
usage down                n= 621  49.8% vs  49.2%           n= 718  49.6% vs  48.8%
usage up / teammate out   n=2722  49.8% vs  49.5%           n=2901  48.9% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 818  Vault's side won 416-402  skill -0.062 z -3.7
  agrees with the news     n= 465  Vault's side won 254-211  skill +0.002 z +0.1
  no news                  n= 759  Vault's side won 383-376  skill -0.044 z -2.6
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 87  toward  53 / away  21  avg move toward +0.36 pts ±0.10
spread  FanDuel     n= 71  toward  43 / away  17  avg move toward +0.33 pts ±0.14
        -> NO-GO: not ahead of the control (+0.03 pts, z +0.2)
total   Pinnacle    n= 44  toward  27 / away  14  avg move toward +0.24 pts ±0.15
total   FanDuel     n= 43  toward  24 / away  14  avg move toward +0.14 pts ±0.16
        -> too few games (44 of 50)
props   Pinnacle    n=252  toward 131 / away  20  net share toward +0.44 ±0.06
props   FanDuel     n= 82  toward  44 / away  11  net share toward +0.40 ±0.10
props   DraftKings  n= 39  toward  13 / away   7  net share toward +0.15 ±0.16
        -> NO-GO: not ahead of the controls (+0.04, z +0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 44  side won  28, price said   21.8  -> tracking (44 of 50)
  all Kalshi-priced lines: n=1262  log-loss Kalshi 0.6827  books 0.6855
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=551  model lean won 275  overs hit 261  | would-be plays 6-10 -4.4u
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
Wk 8     550       38-45 -5.1u     39-44 -6.1u         4-8 -3.9u       4-8 -4.0u
Wk 9     466       40-32 +6.0u     42-30 +6.9u         3-2 +0.6u       3-2 +0.2u
all     4311    441-417 +23.6u   440-418 +4.4u       62-58 +7.5u     63-57 +7.0u
log-loss at the open, same 4311 props: market 0.6850  live model 0.6978  anchored 0.6847
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          17-10         +6.7u           +5.3u       15/26
1-3 days before         18-15         +4.5u           +4.6u        8/32
6-24 hours before       12-14         -2.3u           -2.9u       10/24
under 6 hours           23-13         +8.3u           +4.5u        8/29
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7245 vs 0.6807  skill -0.064 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7187 vs 0.6851  skill -0.049 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7006 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7670 vs 0.7216  skill -0.063 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7066 vs 0.6723  skill -0.051 z -1.2
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6593 vs 0.6433  skill -0.025 z -0.9
Wk  9  props n= 529  LL 0.6999 vs 0.6841  skill -0.023 z -2.0     games n=  36  LL 0.6512 vs 0.6243  skill -0.043 z -1.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
