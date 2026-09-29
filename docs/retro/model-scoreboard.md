# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1654  LL 0.6929 vs 0.6869  skill -0.009 z -1.2    n=1474  LL 0.6927 vs 0.6862  skill -0.009 z -1.3    level with the market (within noise)
pass_att      n=  39  LL 0.7038 vs 0.6846  skill -0.028 z -0.6    n=  39  LL 0.7201 vs 0.6902  skill -0.043 z -0.8    level with the market (within noise)
pass_cmp      n=  58  LL 0.7098 vs 0.6841  skill -0.038 z -1.2    n=  58  LL 0.7101 vs 0.6708  skill -0.059 z -1.9    level with the market (within noise)
pass_td       n=  92  LL 0.6506 vs 0.6671  skill +0.025 z +0.9    n=  90  LL 0.6669 vs 0.6775  skill +0.016 z +0.6    level with the market (within noise)
pass_yd       n=  56  LL 0.7039 vs 0.6936  skill -0.015 z -0.5    n=  56  LL 0.7125 vs 0.6925  skill -0.029 z -0.9    level with the market (within noise)
rec           n= 536  LL 0.6784 vs 0.6715  skill -0.010 z -0.8    n= 526  LL 0.6822 vs 0.6735  skill -0.013 z -1.0    level with the market (within noise)
rec_yd        n= 551  LL 0.6953 vs 0.6938  skill -0.002 z -0.2    n= 404  LL 0.6906 vs 0.6931  skill +0.004 z +0.3    level with the market (within noise)
rush_att      n= 180  LL 0.7256 vs 0.7140  skill -0.016 z -0.7    n= 175  LL 0.7074 vs 0.7049  skill -0.004 z -0.1    level with the market (within noise)
rush_yd       n= 142  LL 0.7095 vs 0.6963  skill -0.019 z -0.6    n= 126  LL 0.7155 vs 0.6997  skill -0.023 z -0.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             192             51%        58%   +2.0
pass_int         95             48%        52%   +0.6
pass_td          16             64%        62%   -0.1
rec              59             55%        66%   +1.7
rec_yd           14             36%        50%   +1.1
rush_yd           8             42%        75%   +1.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        54%    -17.6u         52%    -44.4u
pass_att              67%   +0.4pp        62%     +6.3u         62%     +6.4u
pass_cmp              54%   -0.4pp        45%    -10.7u         47%     -7.0u
pass_td               50%   +0.1pp        59%     +2.1u         59%     +1.5u
pass_yd               67%   -0.0pp        42%    -11.7u         42%    -11.6u
rec                   59%   +0.2pp        58%    +18.1u         54%     -2.4u
rec_yd                57%   -0.0pp        52%     -6.0u         52%     -6.3u
rush_att              65%   +0.9pp        54%     +2.8u         51%     -3.5u
rush_yd               60%   +0.1pp        51%     -2.5u         48%    -11.9u
```

## Game markets (at the close)

```
games   n= 127  LL 0.7020 vs 0.6835  skill -0.027 z -1.1    level with the market (within noise)     beat close   36%  units   -2.3u
ml      n=  36  LL 0.6608 vs 0.6601  skill -0.001 z -0.0    level with the market (within noise)     beat close   50%  units   +4.7u
spread  n=  45  LL 0.7263 vs 0.6926  skill -0.049 z -1.4    level with the market (within noise)     beat close   38%  units   -8.7u
total   n=  46  LL 0.7104 vs 0.6930  skill -0.025 z -0.6    level with the market (within noise)     beat close   24%  units   +1.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  55  32.7% vs  50.1%           n=  62  37.1% vs  50.4%
no news                   n= 684  47.7% vs  49.3%           n= 771  48.0% vs  49.6%
usage down                n= 191  49.7% vs  49.2%           n= 220  47.7% vs  49.0%
usage up / teammate out   n= 809  51.7% vs  49.2%           n= 885  51.3% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 220  Vault's side won 111-109  skill -0.061 z -2.1
  agrees with the news     n= 158  Vault's side won 89-69  skill +0.056 z +1.7
  no news                  n= 243  Vault's side won 136-107  skill -0.011 z -0.4
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
props   Pinnacle    n= 20  toward   7 / away   5  net share toward +0.10 ±0.22
props   FanDuel     n=  2  toward   1 / away   0  net share toward +0.50 ±0.61
props   DraftKings  n=  5  toward   3 / away   0  net share toward +0.60 ±0.36
        -> too few props (20 of 100)
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            3-0         +3.0u           +2.4u         1/2
1-3 days before           4-3         +1.3u           +0.9u         1/6
6-24 hours before         6-4         +2.3u           +2.4u         1/8
under 6 hours            11-7         +2.8u           +0.7u        3/12
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7012 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7236 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6857 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7178 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 587  LL 0.6924 vs 0.6891  skill -0.005 z -0.4     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
