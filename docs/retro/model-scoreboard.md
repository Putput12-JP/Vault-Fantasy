# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2068  LL 0.6957 vs 0.6878  skill -0.011 z -1.8    n=1863  LL 0.6954 vs 0.6884  skill -0.010 z -1.6    level with the market (within noise)
pass_att      n=  58  LL 0.7061 vs 0.6890  skill -0.025 z -0.6    n=  58  LL 0.7110 vs 0.6941  skill -0.024 z -0.6    level with the market (within noise)
pass_cmp      n=  74  LL 0.7022 vs 0.6867  skill -0.023 z -0.9    n=  74  LL 0.7023 vs 0.6757  skill -0.039 z -1.5    level with the market (within noise)
pass_td       n= 110  LL 0.6480 vs 0.6740  skill +0.038 z +1.4    n= 109  LL 0.6686 vs 0.6902  skill +0.031 z +1.2    level with the market (within noise)
pass_yd       n=  75  LL 0.7035 vs 0.6934  skill -0.015 z -0.6    n=  75  LL 0.7074 vs 0.6926  skill -0.021 z -0.8    level with the market (within noise)
rec           n= 650  LL 0.6803 vs 0.6739  skill -0.009 z -0.9    n= 645  LL 0.6822 vs 0.6775  skill -0.007 z -0.6    level with the market (within noise)
rec_yd        n= 672  LL 0.6964 vs 0.6926  skill -0.005 z -0.6    n= 497  LL 0.6927 vs 0.6916  skill -0.002 z -0.1    level with the market (within noise)
rush_att      n= 235  LL 0.7283 vs 0.7102  skill -0.025 z -1.3    n= 229  LL 0.7145 vs 0.7038  skill -0.015 z -0.8    level with the market (within noise)
rush_yd       n= 194  LL 0.7243 vs 0.6969  skill -0.039 z -1.4    n= 176  LL 0.7303 vs 0.6997  skill -0.044 z -1.5    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             233             51%        58%   +2.3
pass_int        115             49%        54%   +1.1
pass_td          20             64%        70%   +0.6
rec              72             55%        64%   +1.5
rec_yd           17             36%        47%   +0.9
rush_yd           9             44%        67%   +1.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -47.0u         51%    -97.1u
pass_att              72%   +0.4pp        62%    +10.3u         62%    +10.3u
pass_cmp              58%   -0.1pp        47%     -9.6u         49%     -6.2u
pass_td               51%   +0.1pp        57%     -0.0u         57%     -0.6u
pass_yd               60%   -0.0pp        43%    -13.7u         45%    -11.8u
rec                   59%   +0.2pp        58%    +24.4u         54%     -4.4u
rec_yd                57%   -0.0pp        52%     -9.4u         52%    -17.0u
rush_att              63%   +0.7pp        52%     -5.0u         49%    -15.7u
rush_yd               59%   +0.1pp        50%     -8.6u         46%    -25.0u
```

## Game markets (at the close)

```
games   n= 155  LL 0.7015 vs 0.6876  skill -0.020 z -1.0    level with the market (within noise)     beat close   32%  units   +2.6u
ml      n=  45  LL 0.6635 vs 0.6742  skill +0.016 z +0.4    level with the market (within noise)     beat close   44%  units   +9.5u
spread  n=  54  LL 0.7102 vs 0.6934  skill -0.024 z -0.8    level with the market (within noise)     beat close   33%  units   -6.3u
total   n=  56  LL 0.7237 vs 0.6926  skill -0.045 z -1.3    level with the market (within noise)     beat close   21%  units   -0.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  69  39.1% vs  49.7%           n=  77  42.9% vs  50.5%
no news                   n= 885  47.3% vs  49.4%           n= 983  47.6% vs  49.7%
usage down                n= 273  53.5% vs  48.8%           n= 315  51.7% vs  48.8%
usage up / teammate out   n= 974  51.8% vs  49.3%           n=1053  51.4% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 263  Vault's side won 133-130  skill -0.059 z -2.2
  agrees with the news     n= 202  Vault's side won 110-92  skill +0.033 z +1.1
  no news                  n= 291  Vault's side won 163-128  skill -0.016 z -0.6
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
props   Pinnacle    n= 29  toward  13 / away   5  net share toward +0.28 ±0.18
props   FanDuel     n=  7  toward   3 / away   1  net share toward +0.29 ±0.36
props   DraftKings  n=  5  toward   3 / away   0  net share toward +0.60 ±0.36
        -> too few props (29 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 11  side won   6, price said    5.2  -> tracking (11 of 50)
  all Kalshi-priced lines: n=161  log-loss Kalshi 0.6976  books 0.7042
Vault vs Kalshi (10+ pts, Kalshi)  n=118  side won  46, price said   60.9  -> no edge yet (z -2.7)
PM sharp $25k+ (all)               n= 17  side won  14, price said    8.5  -> tracking (17 of 50)
PM sharp vs crowd disagree         n=  4  side won   3, price said    1.3  -> tracking (4 of 50)
PM sharp with crowd                n= 10  side won   8, price said    5.6  -> tracking (10 of 50)
Withheld props (teammate out)      lines=82  model lean won 43  overs hit 48  | would-be plays 0-2 -2.0u
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            7-2         +4.9u           +4.1u         6/8
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         6-5         +1.3u           +1.4u         2/9
under 6 hours            11-7         +2.8u           +0.7u        3/12
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 411  LL 0.7109 vs 0.6927  skill -0.026 z -2.0     games n=  28  LL 0.7004 vs 0.7057  skill +0.007 z +0.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
