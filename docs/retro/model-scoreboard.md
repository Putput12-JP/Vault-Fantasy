# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4656  LL 0.7007 vs 0.6860  skill -0.021 z -4.6    n=4267  LL 0.6992 vs 0.6856  skill -0.020 z -4.1    market better than Vault
pass_att      n= 167  LL 0.7094 vs 0.6899  skill -0.028 z -1.2    n= 170  LL 0.7116 vs 0.6952  skill -0.024 z -0.9    level with the market (within noise)
pass_cmp      n= 186  LL 0.7098 vs 0.6880  skill -0.032 z -1.6    n= 187  LL 0.7128 vs 0.6853  skill -0.040 z -1.9    level with the market (within noise)
pass_td       n= 222  LL 0.6578 vs 0.6683  skill +0.016 z +0.8    n= 225  LL 0.6699 vs 0.6799  skill +0.015 z +0.8    level with the market (within noise)
pass_yd       n= 192  LL 0.7258 vs 0.6915  skill -0.050 z -2.3    n= 191  LL 0.7256 vs 0.6931  skill -0.047 z -2.2    market better than Vault
rec           n=1382  LL 0.6875 vs 0.6761  skill -0.017 z -2.0    n=1404  LL 0.6887 vs 0.6757  skill -0.019 z -2.3    market better than Vault
rec_yd        n=1420  LL 0.7046 vs 0.6899  skill -0.021 z -2.6    n=1100  LL 0.7012 vs 0.6897  skill -0.017 z -2.0    market better than Vault
rush_att      n= 560  LL 0.7049 vs 0.6954  skill -0.014 z -1.0    n= 543  LL 0.6939 vs 0.6910  skill -0.004 z -0.3    level with the market (within noise)
rush_yd       n= 527  LL 0.7232 vs 0.6947  skill -0.041 z -2.3    n= 447  LL 0.7263 vs 0.6967  skill -0.042 z -2.2    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             519             51%        54%   +1.3
pass_int        234             49%        51%   +0.6
pass_td          39             64%        64%   +0.0
rec             185             54%        60%   +1.5
rec_yd           41             40%        39%   -0.1
rush_yd          18             46%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.1pp        53%   -105.5u         51%   -193.8u
pass_att              62%   +0.1pp        55%     +9.2u         55%     +7.3u
pass_cmp              59%   +0.2pp        46%    -27.8u         47%    -22.1u
pass_td               49%   -0.1pp        59%     +1.5u         58%     +1.5u
pass_yd               57%   +0.1pp        49%    -16.1u         49%    -17.3u
rec                   59%   +0.2pp        58%    +45.6u         55%    +26.8u
rec_yd                56%   -0.2pp        52%    -26.6u         51%    -58.8u
rush_att              62%   +0.5pp        53%     +1.2u         50%    -22.7u
rush_yd               58%   +0.1pp        45%    -63.8u         45%    -76.3u
```

## Game markets (at the close)

```
games   n= 326  LL 0.6991 vs 0.6823  skill -0.025 z -1.9    level with the market (within noise)     beat close   27%  units  -13.8u
ml      n=  96  LL 0.6557 vs 0.6545  skill -0.002 z -0.1    level with the market (within noise)     beat close   42%  units   +8.2u
spread  n= 113  LL 0.7123 vs 0.6952  skill -0.025 z -1.4    level with the market (within noise)     beat close   22%  units  -19.4u
total   n= 117  LL 0.7220 vs 0.6926  skill -0.042 z -1.8    level with the market (within noise)     beat close   19%  units   -2.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 196  48.5% vs  49.3%           n= 222  47.3% vs  49.2%
no news                   n=1832  48.6% vs  49.4%           n=2006  48.4% vs  49.5%
usage down                n= 561  49.7% vs  49.2%           n= 643  49.6% vs  48.8%
usage up / teammate out   n=2412  50.0% vs  49.4%           n=2571  49.2% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 730  Vault's side won 368-362  skill -0.068 z -3.8
  agrees with the news     n= 410  Vault's side won 221-189  skill -0.001 z -0.0
  no news                  n= 679  Vault's side won 350-329  skill -0.039 z -2.1
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 76  toward  47 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 67  toward  39 / away  17  avg move toward +0.28 pts ±0.14
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
Kalshi vs books (5+ pts apart)     n= 38  side won  25, price said   18.8  -> tracking (38 of 50)
  all Kalshi-priced lines: n=1055  log-loss Kalshi 0.682  books 0.6849
Vault vs Kalshi (10+ pts, Kalshi)  n=167  side won  77, price said   88.8  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=394  model lean won 196  overs hit 196  | would-be plays 6-10 -4.4u
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
Wk 8     500       34-35 +0.7u     34-35 -2.1u         4-7 -2.9u       4-7 -3.0u
all     3795    397-375 +23.4u   393-379 +1.6u       59-55 +7.9u     60-54 +7.7u
log-loss at the open, same 3795 props: market 0.6848  live model 0.6963  anchored 0.6842
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          17-10         +6.7u           +5.3u       15/26
1-3 days before         18-14         +5.5u           +3.7u        8/31
6-24 hours before       12-12         -0.3u           -0.9u        8/22
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
Wk  8  props n= 554  LL 0.7127 vs 0.6853  skill -0.040 z -3.2     games n=  35  LL 0.6373 vs 0.6329  skill -0.007 z -0.3
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
