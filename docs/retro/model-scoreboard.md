# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1649  LL 0.7041 vs 0.6896  skill -0.021 z -2.8    n=1418  LL 0.6969 vs 0.6865  skill -0.015 z -2.0    market better than Vault
pass_att      n=  44  LL 0.7044 vs 0.6884  skill -0.023 z -0.5    n=  44  LL 0.7186 vs 0.6878  skill -0.045 z -0.9    level with the market (within noise)
pass_cmp      n=  64  LL 0.7217 vs 0.6942  skill -0.040 z -1.3    n=  64  LL 0.7208 vs 0.6801  skill -0.060 z -2.0    level with the market (within noise)
pass_td       n=  89  LL 0.6406 vs 0.6654  skill +0.037 z +1.3    n=  89  LL 0.6695 vs 0.6807  skill +0.017 z +0.6    level with the market (within noise)
pass_yd       n=  67  LL 0.7186 vs 0.6934  skill -0.036 z -1.4    n=  66  LL 0.7198 vs 0.6925  skill -0.040 z -1.4    level with the market (within noise)
rec           n= 509  LL 0.6954 vs 0.6821  skill -0.019 z -1.4    n= 505  LL 0.6864 vs 0.6740  skill -0.018 z -1.4    level with the market (within noise)
rec_yd        n= 543  LL 0.7024 vs 0.6912  skill -0.016 z -1.4    n= 347  LL 0.6921 vs 0.6921  skill +0.000 z +0.0    level with the market (within noise)
rush_att      n= 184  LL 0.7417 vs 0.7096  skill -0.045 z -1.9    n= 175  LL 0.7191 vs 0.7039  skill -0.022 z -0.9    level with the market (within noise)
rush_yd       n= 149  LL 0.7169 vs 0.6958  skill -0.030 z -1.0    n= 128  LL 0.7088 vs 0.7001  skill -0.012 z -0.4    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             198             51%        58%   +2.0
pass_int         94             49%        52%   +0.7
pass_td          17             63%        65%   +0.1
rec              59             56%        66%   +1.6
rec_yd           18             41%        44%   +0.3
rush_yd           9             43%        78%   +2.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   60%   +0.2pp        53%    -38.8u         52%    -43.6u
pass_att              74%   +0.8pp        59%     +4.9u         59%     +5.3u
pass_cmp              55%   -0.4pp        41%    -16.4u         42%    -12.6u
pass_td               45%   -0.4pp        59%     +1.7u         57%     -1.7u
pass_yd               73%   -0.0pp        42%    -14.4u         43%    -13.4u
rec                   61%   +0.2pp        57%     +7.3u         54%     +0.6u
rec_yd                57%   -0.0pp        52%     -6.6u         53%     +2.1u
rush_att              64%   +0.9pp        51%     -7.6u         48%    -14.9u
rush_yd               57%   +0.2pp        54%     +4.6u         53%     -0.9u
```

## Game markets (at the close)

```
games   n= 124  LL 0.7024 vs 0.6810  skill -0.032 z -1.4    level with the market (within noise)     beat close   35%  units   -4.1u
ml      n=  35  LL 0.6597 vs 0.6500  skill -0.015 z -0.3    level with the market (within noise)     beat close   49%  units   +2.8u
spread  n=  44  LL 0.7288 vs 0.6931  skill -0.051 z -1.6    level with the market (within noise)     beat close   36%  units   -9.6u
total   n=  45  LL 0.7098 vs 0.6931  skill -0.024 z -0.6    level with the market (within noise)     beat close   22%  units   +2.7u
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 533  LL 0.7157 vs 0.6972  skill -0.027 z -2.2     games n=  40  LL 0.7222 vs 0.6807  skill -0.061 z -1.5
Wk  2  props n= 587  LL 0.6932 vs 0.6837  skill -0.014 z -1.0     games n=  44  LL 0.7165 vs 0.6851  skill -0.046 z -1.1
Wk  3  props n= 529  LL 0.7044 vs 0.6885  skill -0.023 z -1.8     games n=  40  LL 0.6670 vs 0.6768  skill +0.014 z +0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
