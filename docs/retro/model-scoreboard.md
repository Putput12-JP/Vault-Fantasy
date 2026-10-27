# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4054  LL 0.6990 vs 0.6862  skill -0.019 z -3.7    n=3727  LL 0.6986 vs 0.6854  skill -0.019 z -3.7    market better than Vault
pass_att      n= 140  LL 0.7069 vs 0.6869  skill -0.029 z -1.1    n= 143  LL 0.7069 vs 0.6950  skill -0.017 z -0.7    level with the market (within noise)
pass_cmp      n= 159  LL 0.7122 vs 0.6874  skill -0.036 z -1.7    n= 160  LL 0.7151 vs 0.6835  skill -0.046 z -2.1    level with the market (within noise)
pass_td       n= 195  LL 0.6448 vs 0.6652  skill +0.031 z +1.4    n= 198  LL 0.6564 vs 0.6740  skill +0.026 z +1.3    level with the market (within noise)
pass_yd       n= 166  LL 0.7276 vs 0.6941  skill -0.048 z -2.0    n= 166  LL 0.7262 vs 0.6933  skill -0.047 z -2.0    market better than Vault
rec           n=1214  LL 0.6852 vs 0.6769  skill -0.012 z -1.4    n=1237  LL 0.6868 vs 0.6763  skill -0.016 z -1.7    level with the market (within noise)
rec_yd        n=1250  LL 0.7038 vs 0.6890  skill -0.021 z -2.4    n= 972  LL 0.7018 vs 0.6890  skill -0.019 z -2.0    market better than Vault
rush_att      n= 481  LL 0.7092 vs 0.6993  skill -0.014 z -1.0    n= 469  LL 0.6971 vs 0.6929  skill -0.006 z -0.4    level with the market (within noise)
rush_yd       n= 449  LL 0.7181 vs 0.6947  skill -0.034 z -1.7    n= 382  LL 0.7300 vs 0.6967  skill -0.048 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             454             51%        54%   +1.0
pass_int        206             49%        50%   +0.3
pass_td          34             64%        65%   +0.1
rec             162             55%        60%   +1.3
rec_yd           35             40%        40%   +0.0
rush_yd          16             45%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -85.2u         52%   -156.8u
pass_att              62%   +0.2pp        57%    +11.4u         56%     +9.1u
pass_cmp              59%   +0.2pp        46%    -22.7u         47%    -17.0u
pass_td               49%   -0.1pp        59%     +3.7u         59%     +3.6u
pass_yd               57%   +0.1pp        49%    -14.2u         49%    -13.6u
rec                   59%   +0.2pp        58%    +57.4u         55%    +32.0u
rec_yd                56%   -0.1pp        52%    -31.5u         51%    -53.5u
rush_att              63%   +0.7pp        53%     -0.4u         50%    -18.2u
rush_yd               58%   +0.1pp        46%    -51.1u         46%    -60.9u
```

## Game markets (at the close)

```
games   n= 288  LL 0.7033 vs 0.6894  skill -0.020 z -1.5    level with the market (within noise)     beat close   28%  units   -9.6u
ml      n=  86  LL 0.6747 vs 0.6795  skill +0.007 z +0.3    level with the market (within noise)     beat close   43%  units  +11.0u
spread  n=  99  LL 0.7125 vs 0.6950  skill -0.025 z -1.2    level with the market (within noise)     beat close   23%  units  -16.9u
total   n= 103  LL 0.7184 vs 0.6922  skill -0.038 z -1.6    level with the market (within noise)     beat close   19%  units   -3.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 178  48.9% vs  49.4%           n= 200  47.5% vs  49.3%
no news                   n=1488  48.0% vs  49.3%           n=1631  47.9% vs  49.4%
usage down                n= 472  50.8% vs  49.3%           n= 535  50.6% vs  48.9%
usage up / teammate out   n=2246  50.2% vs  49.5%           n=2386  49.2% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 664  Vault's side won 341-323  skill -0.057 z -3.0
  agrees with the news     n= 378  Vault's side won 204-174  skill -0.000 z -0.0
  no news                  n= 577  Vault's side won 300-277  skill -0.035 z -1.7
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 70  toward  42 / away  15  avg move toward +0.48 pts ±0.11
spread  FanDuel     n= 59  toward  33 / away  15  avg move toward +0.29 pts ±0.15
        -> NO-GO: not ahead of the control (+0.18 pts, z +1.0)
total   Pinnacle    n= 35  toward  22 / away  11  avg move toward +0.31 pts ±0.17
total   FanDuel     n= 38  toward  21 / away  12  avg move toward +0.05 pts ±0.15
        -> too few games (35 of 50)
props   Pinnacle    n=173  toward  85 / away  12  net share toward +0.42 ±0.07
props   FanDuel     n= 46  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.10, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 28  side won  16, price said   13.7  -> tracking (28 of 50)
  all Kalshi-priced lines: n=816  log-loss Kalshi 0.6862  books 0.6883
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=300  model lean won 153  overs hit 147  | would-be plays 6-9 -3.4u
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
Wk 7     501       36-36 +1.7u     36-36 -0.3u         3-5 -1.5u       3-5 -1.4u
all     3255    359-336 +23.0u   354-341 +1.7u      55-47 +11.7u    56-46 +11.8u
log-loss at the open, same 3255 props: market 0.6844  live model 0.6951  anchored 0.6836
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           16-9         +6.8u           +5.4u       13/24
1-3 days before         16-13         +4.4u           +4.8u        5/28
6-24 hours before       10-10         -0.2u           -0.7u        6/18
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
Wk  7  props n= 539  LL 0.6861 vs 0.6841  skill -0.003 z -0.2     games n=  38  LL 0.6814 vs 0.6800  skill -0.002 z -0.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
