# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4615  LL 0.7000 vs 0.6860  skill -0.020 z -4.3    n=4231  LL 0.6984 vs 0.6854  skill -0.019 z -4.0    market better than Vault
pass_att      n= 165  LL 0.7061 vs 0.6898  skill -0.024 z -1.0    n= 168  LL 0.7083 vs 0.6951  skill -0.019 z -0.8    level with the market (within noise)
pass_cmp      n= 184  LL 0.7076 vs 0.6883  skill -0.028 z -1.4    n= 185  LL 0.7094 vs 0.6853  skill -0.035 z -1.7    level with the market (within noise)
pass_td       n= 220  LL 0.6568 vs 0.6670  skill +0.015 z +0.8    n= 223  LL 0.6690 vs 0.6784  skill +0.014 z +0.7    level with the market (within noise)
pass_yd       n= 190  LL 0.7242 vs 0.6915  skill -0.047 z -2.2    n= 189  LL 0.7239 vs 0.6931  skill -0.044 z -2.0    market better than Vault
rec           n=1371  LL 0.6881 vs 0.6769  skill -0.017 z -2.0    n=1395  LL 0.6887 vs 0.6757  skill -0.019 z -2.3    level with the market (within noise)
rec_yd        n=1410  LL 0.7042 vs 0.6893  skill -0.022 z -2.7    n=1091  LL 0.7005 vs 0.6890  skill -0.017 z -1.9    market better than Vault
rush_att      n= 554  LL 0.7053 vs 0.6954  skill -0.014 z -1.1    n= 537  LL 0.6944 vs 0.6911  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 521  LL 0.7187 vs 0.6947  skill -0.034 z -1.9    n= 443  LL 0.7245 vs 0.6968  skill -0.040 z -2.1    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             515             51%        54%   +1.3
pass_int        232             49%        51%   +0.6
pass_td          38             64%        66%   +0.2
rec             184             55%        60%   +1.4
rec_yd           41             40%        39%   -0.1
rush_yd          18             46%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -97.9u         52%   -180.8u
pass_att              61%   +0.1pp        55%     +9.3u         55%     +7.5u
pass_cmp              59%   +0.2pp        45%    -27.5u         47%    -22.0u
pass_td               49%   -0.0pp        59%     +1.9u         58%     +1.8u
pass_yd               56%   +0.1pp        50%    -14.1u         49%    -15.3u
rec                   60%   +0.2pp        58%    +45.8u         55%    +29.3u
rec_yd                56%   -0.2pp        52%    -21.3u         51%    -52.6u
rush_att              62%   +0.5pp        53%     -0.2u         50%    -24.3u
rush_yd               59%   +0.1pp        45%    -63.4u         45%    -74.0u
```

## Game markets (at the close)

```
games   n= 323  LL 0.6988 vs 0.6832  skill -0.023 z -1.7    level with the market (within noise)     beat close   27%  units  -10.8u
ml      n=  95  LL 0.6573 vs 0.6576  skill +0.000 z +0.0    level with the market (within noise)     beat close   42%  units   +9.2u
spread  n= 112  LL 0.7112 vs 0.6952  skill -0.023 z -1.3    level with the market (within noise)     beat close   22%  units  -18.4u
total   n= 116  LL 0.7208 vs 0.6927  skill -0.041 z -1.7    level with the market (within noise)     beat close   19%  units   -1.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 196  48.5% vs  49.3%           n= 222  47.3% vs  49.2%
no news                   n=1815  48.5% vs  49.4%           n=1988  48.3% vs  49.5%
usage down                n= 557  49.7% vs  49.2%           n= 638  49.7% vs  48.8%
usage up / teammate out   n=2389  50.1% vs  49.4%           n=2545  49.3% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 721  Vault's side won 363-358  skill -0.067 z -3.7
  agrees with the news     n= 407  Vault's side won 219-188  skill -0.002 z -0.1
  no news                  n= 669  Vault's side won 347-322  skill -0.033 z -1.8
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
  all Kalshi-priced lines: n=1043  log-loss Kalshi 0.6824  books 0.6853
Vault vs Kalshi (10+ pts, Kalshi)  n=167  side won  77, price said   88.8  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=371  model lean won 189  overs hit 182  | would-be plays 6-10 -4.4u
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
Wk 8     464       32-35 -1.4u     32-35 -4.1u         3-7 -3.4u       3-7 -3.7u
all     3759    395-375 +21.2u   391-379 -0.5u       58-55 +7.3u     59-54 +7.1u
log-loss at the open, same 3759 props: market 0.6845  live model 0.6954  anchored 0.6839
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
Wk  8  props n= 513  LL 0.7070 vs 0.6853  skill -0.032 z -2.6     games n=  32  LL 0.6282 vs 0.6380  skill +0.015 z +0.6
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
