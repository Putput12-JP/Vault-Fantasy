# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2924  LL 0.7012 vs 0.6871  skill -0.021 z -3.3    n=2675  LL 0.7006 vs 0.6859  skill -0.021 z -3.4    market better than Vault
pass_att      n=  93  LL 0.7127 vs 0.6878  skill -0.036 z -1.2    n=  94  LL 0.7130 vs 0.6906  skill -0.032 z -1.0    level with the market (within noise)
pass_cmp      n= 111  LL 0.7159 vs 0.6892  skill -0.039 z -1.6    n= 111  LL 0.7176 vs 0.6808  skill -0.054 z -2.1    level with the market (within noise)
pass_td       n= 149  LL 0.6418 vs 0.6700  skill +0.042 z +1.9    n= 150  LL 0.6539 vs 0.6799  skill +0.038 z +1.8    level with the market (within noise)
pass_yd       n= 116  LL 0.7299 vs 0.6940  skill -0.052 z -2.1    n= 116  LL 0.7343 vs 0.6925  skill -0.060 z -2.4    market better than Vault
rec           n= 895  LL 0.6887 vs 0.6783  skill -0.015 z -1.4    n= 895  LL 0.6888 vs 0.6757  skill -0.019 z -1.8    level with the market (within noise)
rec_yd        n= 915  LL 0.7049 vs 0.6891  skill -0.023 z -2.1    n= 702  LL 0.7025 vs 0.6900  skill -0.018 z -1.6    market better than Vault
rush_att      n= 337  LL 0.7186 vs 0.7021  skill -0.024 z -1.3    n= 331  LL 0.7047 vs 0.6957  skill -0.013 z -0.7    level with the market (within noise)
rush_yd       n= 308  LL 0.7171 vs 0.6946  skill -0.032 z -1.3    n= 276  LL 0.7288 vs 0.6973  skill -0.045 z -1.8    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             331             51%        54%   +1.1
pass_int        156             49%        49%   -0.1
pass_td          26             64%        69%   +0.6
rec             110             56%        61%   +1.1
rec_yd           27             39%        44%   +0.6
rush_yd          12             45%        58%   +0.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        52%   -101.7u         51%   -147.6u
pass_att              65%   +0.1pp        57%     +8.2u         57%     +8.7u
pass_cmp              61%   +0.2pp        43%    -21.9u         44%    -18.3u
pass_td               52%   +0.1pp        60%     +6.3u         60%     +6.6u
pass_yd               57%   +0.2pp        42%    -24.8u         43%    -23.6u
rec                   58%   +0.1pp        58%    +30.0u         54%     +5.9u
rec_yd                57%   -0.1pp        53%     -6.7u         52%    -13.7u
rush_att              61%   +0.6pp        51%    -11.4u         48%    -23.5u
rush_yd               54%   +0.1pp        47%    -30.9u         46%    -43.6u
```

## Game markets (at the close)

```
games   n= 213  LL 0.6964 vs 0.6855  skill -0.016 z -0.9    level with the market (within noise)     beat close   29%  units   +1.7u
ml      n=  63  LL 0.6567 vs 0.6687  skill +0.018 z +0.5    level with the market (within noise)     beat close   41%  units  +10.4u
spread  n=  73  LL 0.7048 vs 0.6926  skill -0.018 z -0.7    level with the market (within noise)     beat close   27%  units   -6.2u
total   n=  77  LL 0.7208 vs 0.6924  skill -0.041 z -1.4    level with the market (within noise)     beat close   21%  units   -2.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 129  48.8% vs  49.5%           n= 142  48.6% vs  49.4%
no news                   n=1076  47.8% vs  49.5%           n=1188  48.1% vs  49.6%
usage down                n= 360  50.8% vs  49.1%           n= 413  50.6% vs  48.9%
usage up / teammate out   n=1589  50.2% vs  49.5%           n=1690  49.2% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 469  Vault's side won 238-231  skill -0.070 z -3.0
  agrees with the news     n= 282  Vault's side won 151-131  skill -0.001 z -0.0
  no news                  n= 437  Vault's side won 231-206  skill -0.036 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 29  toward  19 / away   7  avg move toward +0.50 pts ±0.14
spread  FanDuel     n= 22  toward  14 / away   6  avg move toward +0.34 pts ±0.23
        -> too few games (29 of 50)
total   Pinnacle    n= 13  toward   9 / away   3  avg move toward +0.44 pts ±0.22
total   FanDuel     n= 13  toward   9 / away   2  avg move toward +0.19 pts ±0.19
        -> too few games (13 of 50)
props   Pinnacle    n= 61  toward  26 / away   6  net share toward +0.33 ±0.12
props   FanDuel     n= 19  toward   8 / away   4  net share toward +0.21 ±0.22
props   DraftKings  n= 18  toward   8 / away   2  net share toward +0.33 ±0.22
        -> too few props (61 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=351  log-loss Kalshi 0.6827  books 0.6835
Vault vs Kalshi (10+ pts, Kalshi)  n=161  side won  72, price said   85.2  -> no edge yet (z -2.1)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=161  model lean won 86  overs hit 84  | would-be plays 5-8 -3.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     562       54-56 -3.8u     53-57 -9.5u        14-8 +5.2u      14-8 +4.2u
all     2203    276-244 +28.8u   268-252 +6.6u      46-36 +12.5u    47-35 +12.0u
log-loss at the open, same 2203 props: market 0.6844  live model 0.6959  anchored 0.6839
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          12-9         +4.8u           +5.6u        2/20
6-24 hours before        8-10         -1.9u           -2.1u        4/16
under 6 hours           21-13         +6.3u           +2.6u        6/27
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 591  LL 0.6952 vs 0.6791  skill -0.024 z -2.1     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
