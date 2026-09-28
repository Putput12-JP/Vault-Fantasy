# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1587  LL 0.6954 vs 0.6872  skill -0.012 z -1.7    n=1422  LL 0.6946 vs 0.6860  skill -0.013 z -1.7    level with the market (within noise)
pass_att      n=  37  LL 0.7065 vs 0.6871  skill -0.028 z -0.5    n=  37  LL 0.7213 vs 0.6881  skill -0.048 z -0.9    level with the market (within noise)
pass_cmp      n=  56  LL 0.7107 vs 0.6840  skill -0.039 z -1.2    n=  56  LL 0.7110 vs 0.6704  skill -0.061 z -2.0    level with the market (within noise)
pass_td       n=  90  LL 0.6527 vs 0.6721  skill +0.029 z +1.0    n=  88  LL 0.6694 vs 0.6808  skill +0.017 z +0.6    level with the market (within noise)
pass_yd       n=  55  LL 0.7074 vs 0.6936  skill -0.020 z -0.7    n=  55  LL 0.7169 vs 0.6924  skill -0.035 z -1.2    level with the market (within noise)
rec           n= 512  LL 0.6810 vs 0.6716  skill -0.014 z -1.1    n= 507  LL 0.6847 vs 0.6734  skill -0.017 z -1.2    level with the market (within noise)
rec_yd        n= 528  LL 0.6974 vs 0.6925  skill -0.007 z -0.7    n= 388  LL 0.6923 vs 0.6917  skill -0.001 z -0.1    level with the market (within noise)
rush_att      n= 174  LL 0.7294 vs 0.7168  skill -0.018 z -0.7    n= 170  LL 0.7091 vs 0.7058  skill -0.005 z -0.2    level with the market (within noise)
rush_yd       n= 135  LL 0.7126 vs 0.6961  skill -0.024 z -0.7    n= 121  LL 0.7156 vs 0.7001  skill -0.022 z -0.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             183             51%        58%   +2.1
pass_int         93             48%        52%   +0.6
pass_td          15             63%        60%   -0.3
rec              54             56%        68%   +1.8
rec_yd           12             38%        50%   +0.8
rush_yd           8             42%        75%   +1.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   60%   +0.2pp        53%    -26.1u         52%    -48.1u
pass_att              71%   +0.7pp        62%     +6.3u         62%     +6.5u
pass_cmp              54%   -0.4pp        43%    -12.5u         45%     -8.8u
pass_td               49%   -0.1pp        58%     +0.9u         58%     +0.5u
pass_yd               66%   -0.0pp        41%    -12.6u         41%    -12.5u
rec                   59%   +0.2pp        57%     +7.9u         53%    -11.2u
rec_yd                58%   +0.0pp        52%     -5.0u         53%     -4.8u
rush_att              65%   +0.9pp        54%     +1.7u         51%     -3.6u
rush_yd               61%   +0.1pp        52%     -1.3u         49%     -9.7u
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
mixed                     n=  23  17.4% vs  50.0%           n=  29  31.0% vs  49.8%
no news                   n= 776  49.9% vs  49.2%           n= 863  49.8% vs  49.5%
usage down                n= 208  50.5% vs  49.2%           n= 233  48.9% vs  49.4%
usage up / teammate out   n= 667  49.9% vs  49.2%           n= 732  49.7% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 204  Vault's side won 106-98  skill -0.055 z -1.8
  agrees with the news     n= 130  Vault's side won 71-59  skill +0.042 z +1.2
  no news                  n= 267  Vault's side won 145-122  skill -0.019 z -0.7
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            2-0         +2.1u           +1.5u         0/1
1-3 days before           4-3         +1.3u           +0.9u         3/3
6-24 hours before         5-4         +1.4u           +1.4u         1/1
under 6 hours            11-6         +3.8u           +1.7u         4/7
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7012 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7222 vs 0.6807  skill -0.061 z -1.5
Wk  2  props n= 553  LL 0.6857 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7165 vs 0.6851  skill -0.046 z -1.1
Wk  3  props n= 520  LL 0.7001 vs 0.6901  skill -0.014 z -1.1     games n=  40  LL 0.6670 vs 0.6768  skill +0.014 z +0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
