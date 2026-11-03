# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4726  LL 0.7009 vs 0.6858  skill -0.022 z -4.7    n=4332  LL 0.6999 vs 0.6856  skill -0.021 z -4.3    market better than Vault
pass_att      n= 169  LL 0.7087 vs 0.6896  skill -0.028 z -1.2    n= 172  LL 0.7114 vs 0.6951  skill -0.023 z -0.9    level with the market (within noise)
pass_cmp      n= 188  LL 0.7096 vs 0.6878  skill -0.032 z -1.6    n= 189  LL 0.7132 vs 0.6858  skill -0.040 z -1.9    level with the market (within noise)
pass_td       n= 224  LL 0.6584 vs 0.6677  skill +0.014 z +0.7    n= 227  LL 0.6704 vs 0.6792  skill +0.013 z +0.7    level with the market (within noise)
pass_yd       n= 194  LL 0.7275 vs 0.6909  skill -0.053 z -2.5    n= 193  LL 0.7272 vs 0.6923  skill -0.051 z -2.4    market better than Vault
rec           n=1405  LL 0.6869 vs 0.6755  skill -0.017 z -2.0    n=1427  LL 0.6895 vs 0.6763  skill -0.020 z -2.4    market better than Vault
rec_yd        n=1441  LL 0.7043 vs 0.6904  skill -0.020 z -2.5    n=1119  LL 0.7015 vs 0.6899  skill -0.017 z -2.0    market better than Vault
rush_att      n= 569  LL 0.7059 vs 0.6956  skill -0.015 z -1.1    n= 552  LL 0.6946 vs 0.6903  skill -0.006 z -0.5    level with the market (within noise)
rush_yd       n= 536  LL 0.7254 vs 0.6940  skill -0.045 z -2.5    n= 453  LL 0.7281 vs 0.6958  skill -0.046 z -2.4    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             528             51%        54%   +1.0
pass_int        236             49%        51%   +0.6
pass_td          39             64%        64%   +0.0
rec             190             55%        59%   +1.2
rec_yd           41             40%        39%   -0.1
rush_yd          20             46%        40%   -0.5
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.1pp        53%   -127.7u         51%   -215.4u
pass_att              62%   +0.1pp        56%    +11.0u         55%     +9.1u
pass_cmp              60%   +0.2pp        46%    -27.8u         47%    -22.2u
pass_td               49%   -0.1pp        59%     +1.1u         58%     +1.1u
pass_yd               57%   +0.1pp        49%    -18.1u         48%    -19.3u
rec                   60%   +0.2pp        58%    +39.3u         55%    +22.2u
rec_yd                56%   -0.1pp        51%    -38.1u         50%    -71.3u
rush_att              62%   +0.5pp        53%     -2.2u         50%    -26.1u
rush_yd               59%   +0.1pp        45%    -67.9u         45%    -80.8u
```

## Game markets (at the close)

```
games   n= 329  LL 0.7011 vs 0.6830  skill -0.026 z -2.0    market better than Vault                 beat close   27%  units  -16.8u
ml      n=  97  LL 0.6606 vs 0.6576  skill -0.005 z -0.2    level with the market (within noise)     beat close   42%  units   +7.2u
spread  n= 114  LL 0.7137 vs 0.6948  skill -0.027 z -1.5    level with the market (within noise)     beat close   23%  units  -20.4u
total   n= 118  LL 0.7221 vs 0.6926  skill -0.043 z -1.8    level with the market (within noise)     beat close   19%  units   -3.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 223  47.5% vs  49.3%           n= 254  45.7% vs  49.2%
no news                   n=1693  48.4% vs  49.3%           n=1864  48.2% vs  49.4%
usage down                n= 555  50.1% vs  49.2%           n= 633  50.1% vs  48.7%
usage up / teammate out   n=2600  49.8% vs  49.4%           n=2766  48.9% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 778  Vault's side won 396-382  skill -0.063 z -3.6
  agrees with the news     n= 423  Vault's side won 226-197  skill -0.006 z -0.3
  no news                  n= 640  Vault's side won 329-311  skill -0.042 z -2.2
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 77  toward  48 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 68  toward  40 / away  17  avg move toward +0.28 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 39  toward  24 / away  12  avg move toward +0.23 pts ±0.17
total   FanDuel     n= 42  toward  24 / away  13  avg move toward +0.16 pts ±0.16
        -> too few games (39 of 50)
props   Pinnacle    n=231  toward 123 / away  20  net share toward +0.45 ±0.06
props   FanDuel     n= 70  toward  41 / away   9  net share toward +0.46 ±0.11
props   DraftKings  n= 30  toward  10 / away   4  net share toward +0.20 ±0.18
        -> NO-GO: not ahead of the controls (-0.01, z -0.1)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 39  side won  26, price said   19.4  -> tracking (39 of 50)
  all Kalshi-priced lines: n=1087  log-loss Kalshi 0.6822  books 0.6852
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=409  model lean won 205  overs hit 201  | would-be plays 6-10 -4.4u
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
Wk 8     565       38-45 -5.1u     39-44 -6.1u         4-8 -3.9u       4-8 -4.0u
all     3860    401-385 +17.6u   398-388 -2.5u       59-56 +6.9u     60-55 +6.7u
log-loss at the open, same 3860 props: market 0.6848  live model 0.6971  anchored 0.6844
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
Wk  8  props n= 624  LL 0.7128 vs 0.6843  skill -0.042 z -3.4     games n=  38  LL 0.6591 vs 0.6433  skill -0.025 z -0.9
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
