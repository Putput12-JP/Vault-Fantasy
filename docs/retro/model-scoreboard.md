# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3126  LL 0.6993 vs 0.6866  skill -0.018 z -3.1    n=2865  LL 0.6997 vs 0.6863  skill -0.020 z -3.2    market better than Vault
pass_att      n= 102  LL 0.7081 vs 0.6891  skill -0.028 z -1.0    n= 103  LL 0.7107 vs 0.6924  skill -0.026 z -0.9    level with the market (within noise)
pass_cmp      n= 120  LL 0.7162 vs 0.6902  skill -0.038 z -1.6    n= 121  LL 0.7184 vs 0.6821  skill -0.053 z -2.2    level with the market (within noise)
pass_td       n= 157  LL 0.6360 vs 0.6633  skill +0.041 z +1.8    n= 158  LL 0.6501 vs 0.6751  skill +0.037 z +1.7    level with the market (within noise)
pass_yd       n= 126  LL 0.7316 vs 0.6937  skill -0.055 z -2.3    n= 126  LL 0.7352 vs 0.6921  skill -0.062 z -2.6    market better than Vault
rec           n= 945  LL 0.6880 vs 0.6789  skill -0.013 z -1.3    n= 955  LL 0.6889 vs 0.6770  skill -0.018 z -1.7    level with the market (within noise)
rec_yd        n= 975  LL 0.7047 vs 0.6893  skill -0.022 z -2.1    n= 746  LL 0.7020 vs 0.6899  skill -0.018 z -1.6    market better than Vault
rush_att      n= 365  LL 0.7146 vs 0.6994  skill -0.022 z -1.3    n= 358  LL 0.7023 vs 0.6964  skill -0.008 z -0.5    level with the market (within noise)
rush_yd       n= 336  LL 0.7074 vs 0.6923  skill -0.022 z -1.0    n= 298  LL 0.7253 vs 0.6978  skill -0.040 z -1.6    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             351             51%        56%   +1.6
pass_int        166             49%        49%   +0.1
pass_td          27             64%        70%   +0.7
rec             118             55%        63%   +1.6
rec_yd           28             39%        46%   +0.8
rush_yd          12             45%        58%   +0.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -90.9u         51%   -144.5u
pass_att              61%   -0.0pp        58%    +10.8u         58%    +11.4u
pass_cmp              61%   +0.2pp        43%    -24.4u         44%    -20.7u
pass_td               50%   +0.0pp        61%     +8.8u         61%     +9.0u
pass_yd               58%   +0.2pp        43%    -25.7u         43%    -24.4u
rec                   58%   +0.2pp        58%    +32.4u         54%     +8.3u
rec_yd                57%   -0.1pp        53%     -2.1u         52%    -18.8u
rush_att              60%   +0.5pp        52%     -7.4u         49%    -19.5u
rush_yd               55%   +0.1pp        47%    -30.1u         47%    -39.9u
```

## Game markets (at the close)

```
games   n= 227  LL 0.7028 vs 0.6896  skill -0.019 z -1.2    level with the market (within noise)     beat close   29%  units   -9.1u
ml      n=  68  LL 0.6721 vs 0.6817  skill +0.014 z +0.4    level with the market (within noise)     beat close   41%  units   +6.7u
spread  n=  77  LL 0.7080 vs 0.6934  skill -0.021 z -0.8    level with the market (within noise)     beat close   26%  units  -10.2u
total   n=  82  LL 0.7232 vs 0.6927  skill -0.044 z -1.6    level with the market (within noise)     beat close   21%  units   -5.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 129  48.8% vs  49.5%           n= 142  48.6% vs  49.4%
no news                   n=1207  49.0% vs  49.4%           n=1326  48.8% vs  49.6%
usage down                n= 376  50.5% vs  49.1%           n= 429  50.1% vs  48.9%
usage up / teammate out   n=1666  50.1% vs  49.5%           n=1775  49.2% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 496  Vault's side won 256-240  skill -0.060 z -2.7
  agrees with the news     n= 293  Vault's side won 158-135  skill +0.003 z +0.1
  no news                  n= 475  Vault's side won 247-228  skill -0.038 z -1.7
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 54  toward  32 / away  13  avg move toward +0.48 pts ±0.12
spread  FanDuel     n= 44  toward  23 / away  12  avg move toward +0.16 pts ±0.16
        -> NO-GO: not ahead of the control (+0.32 pts, z +1.6)
total   Pinnacle    n= 26  toward  19 / away   6  avg move toward +0.42 pts ±0.21
total   FanDuel     n= 33  toward  19 / away   9  avg move toward +0.13 pts ±0.16
        -> too few games (26 of 50)
props   Pinnacle    n=128  toward  65 / away  10  net share toward +0.43 ±0.08
props   FanDuel     n= 35  toward  16 / away   7  net share toward +0.26 ±0.16
props   DraftKings  n= 23  toward  10 / away   3  net share toward +0.30 ±0.20
        -> NO-GO: not ahead of the controls (+0.13, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=437  log-loss Kalshi 0.6873  books 0.6888
Vault vs Kalshi (10+ pts, Kalshi)  n=164  side won  74, price said   87.0  -> no edge yet (z -2.1)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=171  model lean won 93  overs hit 92  | would-be plays 5-8 -3.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     186       17-16 +0.5u     19-14 +3.3u         3-1 +1.5u       3-1 +1.5u
all     2393    296-261 +31.5u  290-267 +12.3u      49-37 +14.0u    50-36 +13.5u
log-loss at the open, same 2393 props: market 0.6850  live model 0.6953  anchored 0.6841
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           12-8         +3.8u           +3.0u       11/19
1-3 days before         12-10         +3.8u           +4.6u        2/21
6-24 hours before        8-10         -1.9u           -2.1u        4/16
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7250 vs 0.6807  skill -0.065 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7192 vs 0.6851  skill -0.050 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7005 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 196  LL 0.6727 vs 0.6786  skill +0.009 z +0.4     games n=  14  LL 0.7939 vs 0.7528  skill -0.054 z -2.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
