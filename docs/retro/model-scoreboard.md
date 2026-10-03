# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1703  LL 0.6939 vs 0.6869  skill -0.010 z -1.4    n=1524  LL 0.6936 vs 0.6860  skill -0.011 z -1.5    level with the market (within noise)
pass_att      n=  41  LL 0.7069 vs 0.6845  skill -0.033 z -0.6    n=  41  LL 0.7230 vs 0.6907  skill -0.047 z -0.9    level with the market (within noise)
pass_cmp      n=  60  LL 0.7042 vs 0.6851  skill -0.028 z -0.9    n=  60  LL 0.7107 vs 0.6725  skill -0.057 z -1.9    level with the market (within noise)
pass_td       n=  94  LL 0.6480 vs 0.6679  skill +0.030 z +1.0    n=  92  LL 0.6645 vs 0.6790  skill +0.021 z +0.8    level with the market (within noise)
pass_yd       n=  58  LL 0.7036 vs 0.6935  skill -0.015 z -0.5    n=  58  LL 0.7111 vs 0.6925  skill -0.027 z -0.9    level with the market (within noise)
rec           n= 548  LL 0.6789 vs 0.6725  skill -0.009 z -0.8    n= 540  LL 0.6821 vs 0.6734  skill -0.013 z -1.0    level with the market (within noise)
rec_yd        n= 564  LL 0.6972 vs 0.6933  skill -0.006 z -0.5    n= 416  LL 0.6922 vs 0.6924  skill +0.000 z +0.0    level with the market (within noise)
rush_att      n= 188  LL 0.7274 vs 0.7099  skill -0.025 z -1.1    n= 183  LL 0.7115 vs 0.7025  skill -0.013 z -0.6    level with the market (within noise)
rush_yd       n= 150  LL 0.7120 vs 0.6973  skill -0.021 z -0.7    n= 134  LL 0.7159 vs 0.7006  skill -0.022 z -0.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             199             50%        57%   +1.9
pass_int         97             48%        53%   +0.8
pass_td          17             64%        65%   +0.1
rec              61             55%        64%   +1.4
rec_yd           15             36%        47%   +0.8
rush_yd           9             44%        67%   +1.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -30.1u         52%    -58.9u
pass_att              65%   +0.3pp        61%     +6.2u         61%     +6.2u
pass_cmp              54%   -0.4pp        45%    -10.7u         47%     -7.2u
pass_td               50%   +0.1pp        59%     +1.6u         59%     +1.0u
pass_yd               65%   -0.0pp        42%    -11.8u         42%    -11.9u
rec                   59%   +0.1pp        57%    +14.3u         54%     -5.9u
rec_yd                57%   -0.0pp        52%     -7.7u         52%     -7.9u
rush_att              64%   +0.8pp        52%     -1.6u         49%     -9.9u
rush_yd               60%   +0.1pp        51%     -2.9u         48%    -12.3u
```

## Game markets (at the close)

```
games   n= 130  LL 0.7022 vs 0.6855  skill -0.024 z -1.1    level with the market (within noise)     beat close   36%  units   +0.7u
ml      n=  37  LL 0.6645 vs 0.6657  skill +0.002 z +0.0    level with the market (within noise)     beat close   49%  units   +5.9u
spread  n=  46  LL 0.7245 vs 0.6936  skill -0.044 z -1.3    level with the market (within noise)     beat close   39%  units   -7.8u
total   n=  47  LL 0.7100 vs 0.6930  skill -0.025 z -0.6    level with the market (within noise)     beat close   23%  units   +2.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  55  32.7% vs  50.1%           n=  62  37.1% vs  50.4%
no news                   n= 677  47.4% vs  49.2%           n= 762  47.8% vs  49.6%
usage down                n= 203  52.2% vs  49.1%           n= 233  50.2% vs  48.9%
usage up / teammate out   n= 861  52.0% vs  49.3%           n= 937  51.6% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 231  Vault's side won 115-116  skill -0.065 z -2.2
  agrees with the news     n= 179  Vault's side won 99-80  skill +0.044 z +1.4
  no news                  n= 235  Vault's side won 132-103  skill -0.011 z -0.4
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
props   Pinnacle    n= 29  toward  12 / away   5  net share toward +0.24 ±0.18
props   FanDuel     n=  7  toward   3 / away   0  net share toward +0.43 ±0.34
props   DraftKings  n=  5  toward   3 / away   0  net share toward +0.60 ±0.36
        -> too few props (29 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n=  0  side won   0, price said    0.0  -> tracking (0 of 50)
  all Kalshi-priced lines: n=31  log-loss Kalshi 0.6972  books 0.7114
Vault vs Kalshi (10+ pts, Kalshi)  n= 13  side won   6, price said    6.6  -> tracking (13 of 50)
PM sharp $25k+ (all)               n= 13  side won  12, price said    6.9  -> tracking (13 of 50)
PM sharp vs crowd disagree         n=  3  side won   3, price said    1.0  -> tracking (3 of 50)
PM sharp with crowd                n=  9  side won   8, price said    5.2  -> tracking (9 of 50)
Withheld props (teammate out)      lines=36  model lean won 20  overs hit 22  | would-be plays 0-1 -1.0u
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
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7235 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7178 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n=  46  LL 0.7647 vs 0.6963  skill -0.098 z -1.8     games n=   3  LL 0.7114 vs 0.7670  skill +0.072 z +2.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
