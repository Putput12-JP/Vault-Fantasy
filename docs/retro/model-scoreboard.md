# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1613  LL 0.6944 vs 0.6864  skill -0.012 z -1.6    n=1438  LL 0.6940 vs 0.6853  skill -0.013 z -1.7    level with the market (within noise)
pass_att      n=  37  LL 0.7065 vs 0.6871  skill -0.028 z -0.5    n=  37  LL 0.7213 vs 0.6881  skill -0.048 z -0.9    level with the market (within noise)
pass_cmp      n=  56  LL 0.7107 vs 0.6840  skill -0.039 z -1.2    n=  56  LL 0.7110 vs 0.6704  skill -0.061 z -2.0    level with the market (within noise)
pass_td       n=  90  LL 0.6527 vs 0.6721  skill +0.029 z +1.0    n=  88  LL 0.6694 vs 0.6808  skill +0.017 z +0.6    level with the market (within noise)
pass_yd       n=  55  LL 0.7074 vs 0.6936  skill -0.020 z -0.7    n=  55  LL 0.7169 vs 0.6924  skill -0.035 z -1.2    level with the market (within noise)
rec           n= 523  LL 0.6797 vs 0.6710  skill -0.013 z -1.0    n= 514  LL 0.6839 vs 0.6726  skill -0.017 z -1.3    level with the market (within noise)
rec_yd        n= 538  LL 0.6958 vs 0.6919  skill -0.006 z -0.5    n= 394  LL 0.6908 vs 0.6912  skill +0.001 z +0.0    level with the market (within noise)
rush_att      n= 176  LL 0.7277 vs 0.7136  skill -0.020 z -0.8    n= 171  LL 0.7091 vs 0.7039  skill -0.007 z -0.3    level with the market (within noise)
rush_yd       n= 138  LL 0.7140 vs 0.6960  skill -0.026 z -0.8    n= 123  LL 0.7169 vs 0.6999  skill -0.024 z -0.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             186             51%        57%   +1.7
pass_int         93             48%        52%   +0.6
pass_td          15             63%        60%   -0.3
rec              57             56%        65%   +1.4
rec_yd           13             38%        46%   +0.6
rush_yd           8             42%        75%   +1.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -25.6u         52%    -50.4u
pass_att              71%   +0.7pp        62%     +6.3u         62%     +6.5u
pass_cmp              54%   -0.4pp        43%    -12.5u         45%     -8.8u
pass_td               49%   -0.1pp        58%     +0.9u         58%     +0.5u
pass_yd               66%   -0.0pp        41%    -12.6u         41%    -12.5u
rec                   59%   +0.2pp        57%    +11.9u         54%     -6.7u
rec_yd                57%   -0.0pp        52%     -5.3u         53%     -5.5u
rush_att              65%   +0.9pp        53%     +0.7u         51%     -5.6u
rush_yd               60%   +0.1pp        51%     -3.3u         48%    -12.7u
```

## Game markets (at the close)

```
games   n= 124  LL 0.7024 vs 0.6810  skill -0.032 z -1.4    level with the market (within noise)     beat close   35%  units   -4.1u
ml      n=  35  LL 0.6597 vs 0.6500  skill -0.015 z -0.3    level with the market (within noise)     beat close   49%  units   +2.8u
spread  n=  44  LL 0.7288 vs 0.6931  skill -0.051 z -1.6    level with the market (within noise)     beat close   36%  units   -9.6u
total   n=  45  LL 0.7098 vs 0.6931  skill -0.024 z -0.6    level with the market (within noise)     beat close   22%  units   +2.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  55  32.7% vs  50.1%           n=  62  37.1% vs  50.4%
no news                   n= 661  47.7% vs  49.3%           n= 746  48.0% vs  49.6%
usage down                n= 180  50.6% vs  49.1%           n= 207  48.3% vs  49.1%
usage up / teammate out   n= 798  51.4% vs  49.2%           n= 873  51.1% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 220  Vault's side won 111-109  skill -0.061 z -2.1
  agrees with the news     n= 152  Vault's side won 84-68  skill +0.038 z +1.2
  no news                  n= 235  Vault's side won 130-105  skill -0.018 z -0.6
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            2-0         +2.1u           +1.5u         0/1
1-3 days before           4-3         +1.3u           +0.9u         3/3
6-24 hours before         5-4         +1.4u           +1.4u         1/1
under 6 hours            11-7         +2.8u           +0.7u         4/7
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7012 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7222 vs 0.6807  skill -0.061 z -1.5
Wk  2  props n= 553  LL 0.6857 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7165 vs 0.6851  skill -0.046 z -1.1
Wk  3  props n= 546  LL 0.6967 vs 0.6877  skill -0.013 z -1.1     games n=  40  LL 0.6670 vs 0.6768  skill +0.014 z +0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
