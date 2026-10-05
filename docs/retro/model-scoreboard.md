# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2210  LL 0.6964 vs 0.6884  skill -0.012 z -1.9    n=1994  LL 0.6961 vs 0.6883  skill -0.011 z -1.8    level with the market (within noise)
pass_att      n=  65  LL 0.7152 vs 0.6854  skill -0.043 z -1.2    n=  65  LL 0.7255 vs 0.6922  skill -0.048 z -1.2    level with the market (within noise)
pass_cmp      n=  82  LL 0.7099 vs 0.6892  skill -0.030 z -1.1    n=  82  LL 0.7116 vs 0.6763  skill -0.052 z -1.9    level with the market (within noise)
pass_td       n= 118  LL 0.6425 vs 0.6710  skill +0.042 z +1.7    n= 117  LL 0.6617 vs 0.6871  skill +0.037 z +1.5    level with the market (within noise)
pass_yd       n=  83  LL 0.7096 vs 0.6933  skill -0.024 z -1.0    n=  83  LL 0.7139 vs 0.6926  skill -0.031 z -1.3    level with the market (within noise)
rec           n= 690  LL 0.6811 vs 0.6770  skill -0.006 z -0.6    n= 685  LL 0.6823 vs 0.6784  skill -0.006 z -0.5    level with the market (within noise)
rec_yd        n= 711  LL 0.6991 vs 0.6925  skill -0.010 z -1.0    n= 531  LL 0.6969 vs 0.6916  skill -0.008 z -0.8    level with the market (within noise)
rush_att      n= 250  LL 0.7235 vs 0.7081  skill -0.022 z -1.1    n= 242  LL 0.7078 vs 0.7028  skill -0.007 z -0.4    level with the market (within noise)
rush_yd       n= 211  LL 0.7193 vs 0.6968  skill -0.032 z -1.2    n= 189  LL 0.7256 vs 0.6991  skill -0.038 z -1.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             248             51%        58%   +2.0
pass_int        123             49%        53%   +0.9
pass_td          22             64%        68%   +0.5
rec              77             56%        64%   +1.4
rec_yd           17             36%        47%   +0.9
rush_yd           9             44%        67%   +1.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -56.7u         51%   -106.2u
pass_att              67%   +0.2pp        57%     +5.1u         57%     +5.1u
pass_cmp              61%   +0.2pp        46%    -12.0u         48%     -8.5u
pass_td               54%   +0.3pp        58%     +3.1u         58%     +2.0u
pass_yd               63%   -0.0pp        39%    -21.6u         40%    -19.8u
rec                   59%   +0.1pp        58%    +27.1u         54%     -0.8u
rec_yd                55%   -0.0pp        52%    -13.5u         52%    -18.9u
rush_att              63%   +0.7pp        52%     -0.9u         49%    -13.5u
rush_yd               60%   +0.1pp        50%     -8.5u         47%    -24.9u
```

## Game markets (at the close)

```
games   n= 165  LL 0.6997 vs 0.6828  skill -0.025 z -1.2    level with the market (within noise)     beat close   31%  units   -2.3u
ml      n=  48  LL 0.6498 vs 0.6576  skill +0.012 z +0.3    level with the market (within noise)     beat close   44%  units   +7.8u
spread  n=  57  LL 0.7113 vs 0.6941  skill -0.025 z -0.8    level with the market (within noise)     beat close   32%  units   -7.4u
total   n=  60  LL 0.7287 vs 0.6922  skill -0.053 z -1.5    level with the market (within noise)     beat close   20%  units   -2.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  69  39.1% vs  49.7%           n=  77  42.9% vs  50.5%
no news                   n= 960  47.2% vs  49.5%           n=1066  47.6% vs  49.8%
usage down                n= 299  53.5% vs  48.9%           n= 344  51.4% vs  48.8%
usage up / teammate out   n=1029  51.4% vs  49.3%           n=1110  50.9% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 286  Vault's side won 147-139  skill -0.048 z -1.8
  agrees with the news     n= 209  Vault's side won 113-96  skill +0.031 z +1.1
  no news                  n= 315  Vault's side won 174-141  skill -0.022 z -0.9
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
  all Kalshi-priced lines: n=166  log-loss Kalshi 0.6983  books 0.7055
Vault vs Kalshi (10+ pts, Kalshi)  n=146  side won  62, price said   75.5  -> no edge yet (z -2.3)
PM sharp $25k+ (all)               n= 19  side won  16, price said    9.8  -> tracking (19 of 50)
PM sharp vs crowd disagree         n=  4  side won   3, price said    1.3  -> tracking (4 of 50)
PM sharp with crowd                n= 11  side won   9, price said    6.2  -> tracking (11 of 50)
Withheld props (teammate out)      lines=101  model lean won 53  overs hit 53  | would-be plays 0-2 -2.0u
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-2         +5.8u           +5.0u         6/9
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         6-5         +1.3u           +1.4u         2/9
under 6 hours            11-8         +1.8u           -0.3u        3/13
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 553  LL 0.7098 vs 0.6937  skill -0.023 z -2.0     games n=  38  LL 0.6930 vs 0.6801  skill -0.019 z -0.5
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
