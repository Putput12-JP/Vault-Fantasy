# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3754  LL 0.6999 vs 0.6867  skill -0.019 z -3.6    n=3450  LL 0.6997 vs 0.6860  skill -0.020 z -3.6    market better than Vault
pass_att      n= 127  LL 0.7064 vs 0.6882  skill -0.026 z -1.0    n= 130  LL 0.7059 vs 0.6954  skill -0.015 z -0.5    level with the market (within noise)
pass_cmp      n= 147  LL 0.7159 vs 0.6887  skill -0.040 z -1.8    n= 149  LL 0.7171 vs 0.6845  skill -0.048 z -2.1    level with the market (within noise)
pass_td       n= 182  LL 0.6452 vs 0.6681  skill +0.034 z +1.5    n= 185  LL 0.6566 vs 0.6769  skill +0.030 z +1.4    level with the market (within noise)
pass_yd       n= 154  LL 0.7273 vs 0.6938  skill -0.048 z -2.0    n= 154  LL 0.7266 vs 0.6930  skill -0.049 z -2.0    level with the market (within noise)
rec           n=1127  LL 0.6878 vs 0.6784  skill -0.014 z -1.5    n=1141  LL 0.6892 vs 0.6766  skill -0.019 z -2.0    level with the market (within noise)
rec_yd        n=1157  LL 0.7041 vs 0.6885  skill -0.023 z -2.4    n= 895  LL 0.7016 vs 0.6889  skill -0.018 z -1.9    market better than Vault
rush_att      n= 446  LL 0.7103 vs 0.6994  skill -0.016 z -1.0    n= 435  LL 0.6980 vs 0.6944  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 414  LL 0.7155 vs 0.6953  skill -0.029 z -1.4    n= 361  LL 0.7315 vs 0.6974  skill -0.049 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             419             52%        54%   +1.2
pass_int        194             49%        50%   +0.3
pass_td          32             64%        69%   +0.6
rec             146             55%        60%   +1.2
rec_yd           33             40%        42%   +0.3
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -104.3u         51%   -170.3u
pass_att              62%   +0.0pp        58%    +12.7u         56%     +9.0u
pass_cmp              60%   +0.2pp        46%    -21.9u         46%    -18.1u
pass_td               49%   -0.0pp        59%     +2.2u         59%     +3.4u
pass_yd               58%   +0.2pp        48%    -17.0u         48%    -14.9u
rec                   59%   +0.2pp        58%    +36.5u         54%    +12.8u
rec_yd                55%   -0.1pp        52%    -22.8u         51%    -45.0u
rush_att              62%   +0.7pp        53%     -1.6u         50%    -18.0u
rush_yd               56%   +0.0pp        46%    -45.1u         46%    -54.6u
```

## Game markets (at the close)

```
games   n= 267  LL 0.7065 vs 0.6885  skill -0.026 z -1.8    level with the market (within noise)     beat close   28%  units  -18.6u
ml      n=  79  LL 0.6743 vs 0.6771  skill +0.004 z +0.1    level with the market (within noise)     beat close   43%  units   +7.2u
spread  n=  92  LL 0.7151 vs 0.6941  skill -0.030 z -1.4    level with the market (within noise)     beat close   24%  units  -17.6u
total   n=  96  LL 0.7248 vs 0.6926  skill -0.047 z -1.9    level with the market (within noise)     beat close   20%  units   -8.2u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1414  47.3% vs  49.4%           n=1544  47.7% vs  49.5%
usage down                n= 449  49.9% vs  49.3%           n= 510  50.2% vs  48.9%
usage up / teammate out   n=2034  50.4% vs  49.5%           n=2164  49.2% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 611  Vault's side won 311-300  skill -0.063 z -3.2
  agrees with the news     n= 346  Vault's side won 186-160  skill -0.001 z -0.0
  no news                  n= 563  Vault's side won 294-269  skill -0.030 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 66  toward  39 / away  15  avg move toward +0.49 pts ±0.11
spread  FanDuel     n= 55  toward  29 / away  15  avg move toward +0.25 pts ±0.15
        -> NO-GO: not ahead of the control (+0.25 pts, z +1.3)
total   Pinnacle    n= 33  toward  21 / away  10  avg move toward +0.32 pts ±0.18
total   FanDuel     n= 37  toward  21 / away  11  avg move toward +0.08 pts ±0.16
        -> too few games (33 of 50)
props   Pinnacle    n=171  toward  83 / away  12  net share toward +0.41 ±0.07
props   FanDuel     n= 45  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.08, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 21  side won  12, price said   10.3  -> tracking (21 of 50)
  all Kalshi-priced lines: n=689  log-loss Kalshi 0.6867  books 0.6883
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=261  model lean won 125  overs hit 129  | would-be plays 5-9 -4.3u
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
Wk 7     224       15-20 -2.9u     15-20 -4.1u         2-3 -0.6u       2-3 -0.4u
all     2978    338-320 +18.4u   333-325 -2.1u      54-45 +12.7u    55-44 +12.8u
log-loss at the open, same 2978 props: market 0.6850  live model 0.6961  anchored 0.6842
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           15-9         +6.0u           +4.8u       12/23
1-3 days before         14-13         +2.7u           +3.3u        4/26
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
Wk  7  props n= 239  LL 0.6833 vs 0.6905  skill +0.010 z +0.6     games n=  17  LL 0.7045 vs 0.6545  skill -0.076 z -1.7
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
