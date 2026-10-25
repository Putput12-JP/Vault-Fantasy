# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3951  LL 0.7002 vs 0.6868  skill -0.019 z -3.8    n=3629  LL 0.6996 vs 0.6861  skill -0.020 z -3.7    market better than Vault
pass_att      n= 136  LL 0.7073 vs 0.6867  skill -0.030 z -1.1    n= 139  LL 0.7061 vs 0.6943  skill -0.017 z -0.6    level with the market (within noise)
pass_cmp      n= 156  LL 0.7139 vs 0.6882  skill -0.037 z -1.8    n= 157  LL 0.7136 vs 0.6838  skill -0.044 z -2.0    level with the market (within noise)
pass_td       n= 191  LL 0.6477 vs 0.6668  skill +0.029 z +1.3    n= 194  LL 0.6595 vs 0.6763  skill +0.025 z +1.2    level with the market (within noise)
pass_yd       n= 162  LL 0.7270 vs 0.6942  skill -0.047 z -2.0    n= 162  LL 0.7259 vs 0.6935  skill -0.047 z -1.9    level with the market (within noise)
rec           n=1181  LL 0.6869 vs 0.6779  skill -0.013 z -1.4    n=1200  LL 0.6886 vs 0.6769  skill -0.017 z -1.9    level with the market (within noise)
rec_yd        n=1214  LL 0.7046 vs 0.6893  skill -0.022 z -2.5    n= 941  LL 0.7022 vs 0.6892  skill -0.019 z -2.0    market better than Vault
rush_att      n= 471  LL 0.7102 vs 0.6996  skill -0.015 z -1.0    n= 460  LL 0.6978 vs 0.6939  skill -0.006 z -0.4    level with the market (within noise)
rush_yd       n= 440  LL 0.7183 vs 0.6955  skill -0.033 z -1.7    n= 376  LL 0.7313 vs 0.6973  skill -0.049 z -2.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             439             51%        54%   +1.1
pass_int        202             49%        50%   +0.1
pass_td          34             64%        65%   +0.1
rec             154             55%        61%   +1.5
rec_yd           34             40%        41%   +0.2
rush_yd          15             45%        47%   +0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -81.7u         52%   -154.4u
pass_att              61%   +0.2pp        57%    +11.5u         56%     +9.2u
pass_cmp              59%   +0.2pp        46%    -21.5u         47%    -17.6u
pass_td               50%   -0.0pp        59%     +0.9u         58%     +0.7u
pass_yd               57%   +0.1pp        49%    -13.7u         49%    -13.3u
rec                   59%   +0.2pp        58%    +53.5u         55%    +29.1u
rec_yd                55%   -0.1pp        52%    -24.4u         51%    -46.3u
rush_att              63%   +0.7pp        53%     +0.7u         50%    -17.1u
rush_yd               57%   +0.1pp        46%    -49.0u         46%    -59.5u
```

## Game markets (at the close)

```
games   n= 282  LL 0.7064 vs 0.6905  skill -0.023 z -1.7    level with the market (within noise)     beat close   28%  units  -14.4u
ml      n=  84  LL 0.6806 vs 0.6835  skill +0.004 z +0.1    level with the market (within noise)     beat close   43%  units   +9.9u
spread  n=  97  LL 0.7152 vs 0.6945  skill -0.030 z -1.5    level with the market (within noise)     beat close   23%  units  -18.7u
total   n= 101  LL 0.7193 vs 0.6924  skill -0.039 z -1.6    level with the market (within noise)     beat close   20%  units   -5.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1546  47.8% vs  49.4%           n=1685  48.1% vs  49.5%
usage down                n= 475  50.9% vs  49.2%           n= 538  50.7% vs  48.9%
usage up / teammate out   n=2083  50.6% vs  49.5%           n=2220  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 632  Vault's side won 321-311  skill -0.064 z -3.3
  agrees with the news     n= 359  Vault's side won 193-166  skill -0.004 z -0.1
  no news                  n= 598  Vault's side won 310-288  skill -0.033 z -1.6
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
Kalshi vs books (5+ pts apart)     n= 25  side won  14, price said   12.3  -> tracking (25 of 50)
  all Kalshi-priced lines: n=774  log-loss Kalshi 0.6876  books 0.6891
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=279  model lean won 138  overs hit 139  | would-be plays 6-9 -3.4u
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
Wk 7     403       26-33 -5.6u     26-33 -6.6u         2-5 -2.5u       2-5 -2.4u
all     3157    349-333 +15.7u   344-338 -4.5u      54-47 +10.7u    55-46 +10.8u
log-loss at the open, same 3157 props: market 0.6851  live model 0.6962  anchored 0.6844
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           16-9         +6.8u           +5.4u       13/24
1-3 days before         15-13         +3.6u           +4.2u        5/27
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
Wk  7  props n= 436  LL 0.6935 vs 0.6894  skill -0.006 z -0.4     games n=  32  LL 0.7043 vs 0.6876  skill -0.024 z -0.8
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
