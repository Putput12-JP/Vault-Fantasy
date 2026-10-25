# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3609  LL 0.7009 vs 0.6863  skill -0.021 z -3.9    n=3311  LL 0.7009 vs 0.6861  skill -0.021 z -3.8    market better than Vault
pass_att      n= 121  LL 0.7160 vs 0.6887  skill -0.040 z -1.4    n= 123  LL 0.7160 vs 0.6944  skill -0.031 z -1.1    level with the market (within noise)
pass_cmp      n= 141  LL 0.7200 vs 0.6898  skill -0.044 z -2.0    n= 142  LL 0.7197 vs 0.6845  skill -0.051 z -2.2    level with the market (within noise)
pass_td       n= 177  LL 0.6479 vs 0.6675  skill +0.029 z +1.3    n= 179  LL 0.6591 vs 0.6762  skill +0.025 z +1.2    level with the market (within noise)
pass_yd       n= 147  LL 0.7343 vs 0.6935  skill -0.059 z -2.4    n= 147  LL 0.7338 vs 0.6926  skill -0.059 z -2.4    market better than Vault
rec           n=1087  LL 0.6881 vs 0.6779  skill -0.015 z -1.6    n=1097  LL 0.6900 vs 0.6762  skill -0.021 z -2.1    level with the market (within noise)
rec_yd        n=1115  LL 0.7057 vs 0.6888  skill -0.025 z -2.6    n= 860  LL 0.7027 vs 0.6897  skill -0.019 z -1.9    market better than Vault
rush_att      n= 426  LL 0.7104 vs 0.6989  skill -0.017 z -1.0    n= 416  LL 0.6972 vs 0.6955  skill -0.002 z -0.1    level with the market (within noise)
rush_yd       n= 395  LL 0.7125 vs 0.6930  skill -0.028 z -1.4    n= 347  LL 0.7294 vs 0.6975  skill -0.046 z -2.0    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             401             51%        55%   +1.4
pass_int        187             49%        50%   +0.2
pass_td          30             64%        70%   +0.7
rec             139             55%        61%   +1.4
rec_yd           31             39%        45%   +0.7
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%   -111.8u         51%   -178.9u
pass_att              63%   +0.1pp        57%    +10.1u         55%     +6.6u
pass_cmp              61%   +0.2pp        45%    -22.5u         46%    -18.6u
pass_td               51%   +0.1pp        59%     +3.6u         59%     +4.5u
pass_yd               58%   +0.2pp        45%    -22.9u         46%    -21.2u
rec                   59%   +0.2pp        57%    +27.8u         54%     +7.2u
rec_yd                56%   -0.1pp        52%    -15.3u         51%    -39.2u
rush_att              62%   +0.6pp        53%     +0.2u         50%    -17.7u
rush_yd               57%   +0.1pp        47%    -40.3u         46%    -51.9u
```

## Game markets (at the close)

```
games   n= 256  LL 0.7080 vs 0.6896  skill -0.027 z -1.8    level with the market (within noise)     beat close   29%  units  -15.2u
ml      n=  76  LL 0.6750 vs 0.6811  skill +0.009 z +0.3    level with the market (within noise)     beat close   45%  units  +10.2u
spread  n=  88  LL 0.7148 vs 0.6941  skill -0.030 z -1.4    level with the market (within noise)     beat close   25%  units  -15.4u
total   n=  92  LL 0.7289 vs 0.6923  skill -0.053 z -2.1    market better than Vault                 beat close   18%  units   -9.9u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1320  47.9% vs  49.4%           n=1446  48.1% vs  49.5%
usage down                n= 428  50.7% vs  49.2%           n= 488  50.6% vs  48.8%
usage up / teammate out   n=1982  50.7% vs  49.5%           n=2111  49.5% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 593  Vault's side won 301-292  skill -0.066 z -3.2
  agrees with the news     n= 336  Vault's side won 179-157  skill -0.005 z -0.2
  no news                  n= 525  Vault's side won 270-255  skill -0.038 z -1.8
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 63  toward  36 / away  15  avg move toward +0.44 pts ±0.11
spread  FanDuel     n= 52  toward  26 / away  15  avg move toward +0.17 pts ±0.15
        -> NO-GO: not ahead of the control (+0.27 pts, z +1.5)
total   Pinnacle    n= 32  toward  21 / away  10  avg move toward +0.33 pts ±0.19
total   FanDuel     n= 37  toward  21 / away  11  avg move toward +0.08 pts ±0.16
        -> too few games (32 of 50)
props   Pinnacle    n=171  toward  81 / away  12  net share toward +0.40 ±0.07
props   FanDuel     n= 45  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.07, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 18  side won  10, price said    8.6  -> tracking (18 of 50)
  all Kalshi-priced lines: n=631  log-loss Kalshi 0.6879  books 0.6891
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=225  model lean won 109  overs hit 112  | would-be plays 5-9 -4.3u
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
Wk 7      85         5-8 -2.5u       5-8 -2.6u         0-2 -2.0u       0-2 -2.0u
all     2839    328-308 +18.8u   323-313 -0.6u      52-44 +11.2u    53-43 +11.2u
log-loss at the open, same 2839 props: market 0.6850  live model 0.6973  anchored 0.6845
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           13-9         +3.9u           +2.9u       12/21
1-3 days before         14-12         +3.7u           +4.3u        3/25
6-24 hours before        9-10         -0.8u           -1.2u        5/17
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
Wk  7  props n=  94  LL 0.6993 vs 0.6810  skill -0.027 z -1.0     games n=   6  LL 0.7659 vs 0.6371  skill -0.202 z -2.7
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
