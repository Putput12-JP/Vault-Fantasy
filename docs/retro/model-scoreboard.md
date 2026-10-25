# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3994  LL 0.6999 vs 0.6867  skill -0.019 z -3.7    n=3672  LL 0.6995 vs 0.6860  skill -0.020 z -3.7    market better than Vault
pass_att      n= 138  LL 0.7073 vs 0.6872  skill -0.029 z -1.1    n= 141  LL 0.7068 vs 0.6948  skill -0.017 z -0.6    level with the market (within noise)
pass_cmp      n= 158  LL 0.7124 vs 0.6878  skill -0.036 z -1.7    n= 159  LL 0.7153 vs 0.6838  skill -0.046 z -2.1    level with the market (within noise)
pass_td       n= 193  LL 0.6471 vs 0.6667  skill +0.029 z +1.4    n= 196  LL 0.6587 vs 0.6760  skill +0.025 z +1.2    level with the market (within noise)
pass_yd       n= 164  LL 0.7278 vs 0.6939  skill -0.049 z -2.0    n= 164  LL 0.7266 vs 0.6934  skill -0.048 z -2.0    market better than Vault
rec           n=1194  LL 0.6867 vs 0.6777  skill -0.013 z -1.5    n=1214  LL 0.6883 vs 0.6767  skill -0.017 z -1.9    level with the market (within noise)
rec_yd        n=1228  LL 0.7048 vs 0.6895  skill -0.022 z -2.5    n= 954  LL 0.7028 vs 0.6897  skill -0.019 z -2.0    market better than Vault
rush_att      n= 475  LL 0.7090 vs 0.6990  skill -0.014 z -1.0    n= 464  LL 0.6967 vs 0.6935  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 444  LL 0.7183 vs 0.6953  skill -0.033 z -1.7    n= 380  LL 0.7309 vs 0.6971  skill -0.049 z -2.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             445             51%        54%   +1.1
pass_int        204             49%        50%   +0.1
pass_td          34             64%        65%   +0.1
rec             156             55%        62%   +1.6
rec_yd           34             40%        41%   +0.2
rush_yd          16             45%        44%   -0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -84.9u         52%   -152.9u
pass_att              62%   +0.2pp        57%    +11.5u         56%     +9.2u
pass_cmp              59%   +0.2pp        46%    -23.5u         47%    -17.8u
pass_td               50%   -0.0pp        59%     +2.6u         58%     +2.3u
pass_yd               57%   +0.1pp        49%    -13.9u         49%    -13.4u
rec                   59%   +0.2pp        58%    +53.2u         55%    +30.9u
rec_yd                56%   -0.1pp        52%    -27.9u         51%    -48.9u
rush_att              63%   +0.7pp        53%     +2.0u         50%    -15.8u
rush_yd               58%   +0.1pp        46%    -49.1u         46%    -59.6u
```

## Game markets (at the close)

```
games   n= 285  LL 0.7048 vs 0.6900  skill -0.021 z -1.6    level with the market (within noise)     beat close   27%  units  -12.1u
ml      n=  85  LL 0.6776 vs 0.6813  skill +0.005 z +0.2    level with the market (within noise)     beat close   42%  units  +10.3u
spread  n=  98  LL 0.7139 vs 0.6949  skill -0.027 z -1.4    level with the market (within noise)     beat close   22%  units  -17.8u
total   n= 102  LL 0.7188 vs 0.6924  skill -0.038 z -1.6    level with the market (within noise)     beat close   20%  units   -4.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1578  48.1% vs  49.4%           n=1718  48.3% vs  49.5%
usage down                n= 484  51.0% vs  49.2%           n= 546  50.7% vs  48.9%
usage up / teammate out   n=2091  50.6% vs  49.5%           n=2228  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 633  Vault's side won 322-311  skill -0.064 z -3.3
  agrees with the news     n= 362  Vault's side won 194-168  skill -0.005 z -0.2
  no news                  n= 611  Vault's side won 320-291  skill -0.030 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 68  toward  40 / away  15  avg move toward +0.48 pts ±0.11
spread  FanDuel     n= 58  toward  32 / away  15  avg move toward +0.30 pts ±0.15
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.0)
total   Pinnacle    n= 34  toward  21 / away  11  avg move toward +0.30 pts ±0.18
total   FanDuel     n= 38  toward  21 / away  12  avg move toward +0.05 pts ±0.15
        -> too few games (34 of 50)
props   Pinnacle    n=173  toward  84 / away  12  net share toward +0.42 ±0.07
props   FanDuel     n= 45  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.08, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 27  side won  15, price said   13.3  -> tracking (27 of 50)
  all Kalshi-priced lines: n=791  log-loss Kalshi 0.6871  books 0.689
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=283  model lean won 142  overs hit 141  | would-be plays 6-9 -3.4u
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
Wk 7     446       31-35 -1.8u     31-35 -3.9u         3-5 -1.5u       3-5 -1.4u
all     3200    354-335 +19.5u   349-340 -1.8u      55-47 +11.7u    56-46 +11.8u
log-loss at the open, same 3200 props: market 0.6851  live model 0.6962  anchored 0.6843
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
Wk  7  props n= 479  LL 0.6921 vs 0.6883  skill -0.005 z -0.4     games n=  35  LL 0.6916 vs 0.6837  skill -0.012 z -0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
