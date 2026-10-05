# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2294  LL 0.6971 vs 0.6893  skill -0.011 z -1.9    n=2074  LL 0.6962 vs 0.6884  skill -0.011 z -1.8    level with the market (within noise)
pass_att      n=  67  LL 0.7147 vs 0.6860  skill -0.042 z -1.2    n=  67  LL 0.7268 vs 0.6920  skill -0.050 z -1.3    level with the market (within noise)
pass_cmp      n=  84  LL 0.7085 vs 0.6893  skill -0.028 z -1.1    n=  84  LL 0.7109 vs 0.6779  skill -0.049 z -1.8    level with the market (within noise)
pass_td       n= 120  LL 0.6456 vs 0.6734  skill +0.041 z +1.7    n= 119  LL 0.6644 vs 0.6886  skill +0.035 z +1.4    level with the market (within noise)
pass_yd       n=  85  LL 0.7111 vs 0.6933  skill -0.026 z -1.1    n=  85  LL 0.7161 vs 0.6926  skill -0.034 z -1.5    level with the market (within noise)
rec           n= 715  LL 0.6827 vs 0.6793  skill -0.005 z -0.5    n= 710  LL 0.6821 vs 0.6782  skill -0.006 z -0.6    level with the market (within noise)
rec_yd        n= 736  LL 0.6983 vs 0.6923  skill -0.009 z -0.9    n= 553  LL 0.6964 vs 0.6916  skill -0.007 z -0.7    level with the market (within noise)
rush_att      n= 263  LL 0.7212 vs 0.7092  skill -0.017 z -0.9    n= 255  LL 0.7053 vs 0.7033  skill -0.003 z -0.1    level with the market (within noise)
rush_yd       n= 224  LL 0.7237 vs 0.6960  skill -0.040 z -1.5    n= 201  LL 0.7273 vs 0.6983  skill -0.042 z -1.5    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             265             51%        56%   +1.5
pass_int        125             49%        52%   +0.7
pass_td          22             64%        68%   +0.5
rec              87             56%        60%   +0.8
rec_yd           21             38%        48%   +0.9
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        52%    -75.6u         51%   -126.5u
pass_att              68%   +0.2pp        55%     +3.1u         55%     +3.1u
pass_cmp              61%   +0.1pp        45%    -14.0u         46%    -10.5u
pass_td               55%   +0.3pp        58%     +2.9u         58%     +1.8u
pass_yd               64%   -0.0pp        38%    -23.6u         40%    -21.8u
rec                   59%   +0.1pp        58%    +25.2u         54%     -1.2u
rec_yd                54%   -0.0pp        52%    -10.7u         52%    -19.2u
rush_att              62%   +0.6pp        53%     +1.1u         50%    -10.2u
rush_yd               59%   +0.1pp        48%    -17.0u         45%    -34.3u
```

## Game markets (at the close)

```
games   n= 168  LL 0.6985 vs 0.6850  skill -0.020 z -1.0    level with the market (within noise)     beat close   31%  units   +1.2u
ml      n=  49  LL 0.6508 vs 0.6653  skill +0.022 z +0.5    level with the market (within noise)     beat close   43%  units   +9.4u
spread  n=  58  LL 0.7078 vs 0.6940  skill -0.020 z -0.7    level with the market (within noise)     beat close   31%  units   -6.5u
total   n=  61  LL 0.7279 vs 0.6922  skill -0.051 z -1.5    level with the market (within noise)     beat close   21%  units   -1.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  93  49.5% vs  49.5%           n= 103  49.5% vs  49.9%
no news                   n= 837  46.9% vs  49.4%           n= 935  47.6% vs  49.7%
usage down                n= 290  51.4% vs  48.9%           n= 334  50.0% vs  48.7%
usage up / teammate out   n=1229  50.5% vs  49.5%           n=1322  49.8% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 326  Vault's side won 166-160  skill -0.051 z -2.1
  agrees with the news     n= 229  Vault's side won 119-110  skill +0.008 z +0.3
  no news                  n= 284  Vault's side won 162-122  skill -0.002 z -0.1
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
props   Pinnacle    n= 30  toward  13 / away   5  net share toward +0.27 ±0.18
props   FanDuel     n=  7  toward   3 / away   1  net share toward +0.29 ±0.36
props   DraftKings  n=  5  toward   3 / away   0  net share toward +0.60 ±0.36
        -> too few props (30 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 12  side won   7, price said    5.6  -> tracking (12 of 50)
  all Kalshi-priced lines: n=183  log-loss Kalshi 0.6941  books 0.7028
Vault vs Kalshi (10+ pts, Kalshi)  n=158  side won  67, price said   81.6  -> no edge yet (z -2.3)
PM sharp $25k+ (all)               n= 19  side won  16, price said    9.8  -> tracking (19 of 50)
PM sharp vs crowd disagree         n=  4  side won   3, price said    1.3  -> tracking (4 of 50)
PM sharp with crowd                n= 11  side won   9, price said    6.2  -> tracking (11 of 50)
Withheld props (teammate out)      lines=105  model lean won 54  overs hit 53  | would-be plays 0-3 -3.0u
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-2         +5.8u           +5.0u         6/9
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         6-5         +1.3u           +1.4u         2/9
under 6 hours            13-9         +2.5u           +0.4u        4/16
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 637  LL 0.7106 vs 0.6962  skill -0.021 z -1.9     games n=  41  LL 0.6882 vs 0.6894  skill +0.002 z +0.0
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
