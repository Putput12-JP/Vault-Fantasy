# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3567  LL 0.7008 vs 0.6862  skill -0.021 z -3.9    n=3269  LL 0.7011 vs 0.6861  skill -0.022 z -3.9    market better than Vault
pass_att      n= 119  LL 0.7164 vs 0.6881  skill -0.041 z -1.5    n= 121  LL 0.7167 vs 0.6936  skill -0.033 z -1.1    level with the market (within noise)
pass_cmp      n= 139  LL 0.7204 vs 0.6891  skill -0.045 z -2.0    n= 140  LL 0.7201 vs 0.6842  skill -0.052 z -2.3    market better than Vault
pass_td       n= 176  LL 0.6458 vs 0.6676  skill +0.033 z +1.5    n= 177  LL 0.6583 vs 0.6773  skill +0.028 z +1.3    level with the market (within noise)
pass_yd       n= 145  LL 0.7369 vs 0.6929  skill -0.063 z -2.5    n= 145  LL 0.7360 vs 0.6926  skill -0.063 z -2.5    market better than Vault
rec           n=1076  LL 0.6879 vs 0.6779  skill -0.015 z -1.5    n=1087  LL 0.6901 vs 0.6761  skill -0.021 z -2.1    level with the market (within noise)
rec_yd        n=1102  LL 0.7054 vs 0.6886  skill -0.025 z -2.5    n= 848  LL 0.7025 vs 0.6895  skill -0.019 z -1.8    market better than Vault
rush_att      n= 420  LL 0.7098 vs 0.6990  skill -0.015 z -1.0    n= 410  LL 0.6966 vs 0.6957  skill -0.001 z -0.1    level with the market (within noise)
rush_yd       n= 390  LL 0.7131 vs 0.6926  skill -0.030 z -1.4    n= 341  LL 0.7321 vs 0.6979  skill -0.049 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             397             51%        55%   +1.3
pass_int        185             49%        50%   +0.2
pass_td          30             64%        70%   +0.7
rec             137             55%        61%   +1.3
rec_yd           31             39%        45%   +0.7
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%   -117.9u         51%   -185.4u
pass_att              64%   +0.1pp        57%    +10.1u         55%     +6.6u
pass_cmp              61%   +0.2pp        45%    -22.5u         46%    -18.6u
pass_td               51%   +0.1pp        59%     +4.0u         59%     +4.6u
pass_yd               59%   +0.2pp        45%    -24.5u         45%    -23.1u
rec                   59%   +0.2pp        57%    +29.8u         54%     +8.2u
rec_yd                56%   -0.1pp        52%    -14.7u         51%    -37.9u
rush_att              62%   +0.6pp        53%     -1.3u         50%    -17.5u
rush_yd               57%   +0.1pp        46%    -41.5u         46%    -53.9u
```

## Game markets (at the close)

```
games   n= 253  LL 0.7083 vs 0.6901  skill -0.026 z -1.8    level with the market (within noise)     beat close   29%  units  -15.7u
ml      n=  75  LL 0.6771 vs 0.6831  skill +0.009 z +0.3    level with the market (within noise)     beat close   45%  units   +9.6u
spread  n=  87  LL 0.7152 vs 0.6940  skill -0.030 z -1.4    level with the market (within noise)     beat close   25%  units  -16.4u
total   n=  91  LL 0.7275 vs 0.6922  skill -0.051 z -2.0    level with the market (within noise)     beat close   19%  units   -8.9u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1293  47.9% vs  49.4%           n=1420  48.0% vs  49.6%
usage down                n= 418  50.7% vs  49.2%           n= 477  50.3% vs  48.8%
usage up / teammate out   n=1970  50.8% vs  49.5%           n=2099  49.5% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 587  Vault's side won 297-290  skill -0.067 z -3.3
  agrees with the news     n= 332  Vault's side won 177-155  skill -0.005 z -0.2
  no news                  n= 514  Vault's side won 266-248  skill -0.038 z -1.7
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 62  toward  36 / away  15  avg move toward +0.45 pts ±0.11
spread  FanDuel     n= 51  toward  26 / away  14  avg move toward +0.18 pts ±0.15
        -> NO-GO: not ahead of the control (+0.27 pts, z +1.5)
total   Pinnacle    n= 31  toward  21 / away   9  avg move toward +0.38 pts ±0.18
total   FanDuel     n= 37  toward  21 / away  11  avg move toward +0.08 pts ±0.16
        -> too few games (31 of 50)
props   Pinnacle    n=149  toward  72 / away  12  net share toward +0.40 ±0.07
props   FanDuel     n= 41  toward  19 / away   8  net share toward +0.27 ±0.15
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.14, z +0.8)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 18  side won  10, price said    8.6  -> tracking (18 of 50)
  all Kalshi-priced lines: n=611  log-loss Kalshi 0.6881  books 0.6895
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
Wk 7      43         3-5 -1.6u       3-5 -1.7u         0-1 -1.0u       0-1 -1.0u
all     2797    326-305 +19.7u   321-310 +0.4u      52-43 +12.2u    53-42 +12.2u
log-loss at the open, same 2797 props: market 0.6850  live model 0.6975  anchored 0.6845
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           13-9         +3.9u           +2.9u       12/21
1-3 days before         14-11         +4.7u           +5.3u        3/24
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
Wk  7  props n=  52  LL 0.6883 vs 0.6651  skill -0.035 z -0.8     games n=   3  LL 0.8496 vs 0.6315  skill -0.345 z -5.3
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
