# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2795  LL 0.7009 vs 0.6871  skill -0.020 z -3.2    n=2557  LL 0.6996 vs 0.6862  skill -0.020 z -3.0    market better than Vault
pass_att      n=  89  LL 0.7099 vs 0.6873  skill -0.033 z -1.1    n=  90  LL 0.7122 vs 0.6909  skill -0.031 z -0.9    level with the market (within noise)
pass_cmp      n= 108  LL 0.7155 vs 0.6892  skill -0.038 z -1.6    n= 108  LL 0.7182 vs 0.6811  skill -0.054 z -2.1    level with the market (within noise)
pass_td       n= 144  LL 0.6304 vs 0.6639  skill +0.051 z +2.3    n= 145  LL 0.6431 vs 0.6739  skill +0.046 z +2.2    Vault better than the market
pass_yd       n= 111  LL 0.7298 vs 0.6939  skill -0.052 z -2.0    n= 111  LL 0.7333 vs 0.6924  skill -0.059 z -2.3    market better than Vault
rec           n= 854  LL 0.6894 vs 0.6788  skill -0.016 z -1.4    n= 854  LL 0.6891 vs 0.6767  skill -0.018 z -1.6    level with the market (within noise)
rec_yd        n= 875  LL 0.7057 vs 0.6895  skill -0.023 z -2.0    n= 670  LL 0.7032 vs 0.6908  skill -0.018 z -1.5    market better than Vault
rush_att      n= 323  LL 0.7177 vs 0.7030  skill -0.021 z -1.1    n= 317  LL 0.7029 vs 0.6963  skill -0.009 z -0.5    level with the market (within noise)
rush_yd       n= 291  LL 0.7179 vs 0.6943  skill -0.034 z -1.4    n= 262  LL 0.7259 vs 0.6977  skill -0.040 z -1.6    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             314             51%        55%   +1.5
pass_int        151             49%        48%   -0.2
pass_td          26             64%        69%   +0.6
rec             101             55%        63%   +1.6
rec_yd           25             39%        48%   +1.0
rush_yd          11             45%        64%   +1.3
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -90.2u         51%   -144.9u
pass_att              66%   +0.2pp        58%     +8.6u         58%     +8.8u
pass_cmp              60%   +0.1pp        44%    -20.7u         44%    -17.1u
pass_td               53%   +0.1pp        61%     +7.5u         61%     +7.6u
pass_yd               59%   +0.2pp        42%    -23.5u         43%    -22.2u
rec                   58%   +0.1pp        58%    +30.0u         54%     +2.9u
rec_yd                56%   -0.1pp        52%     -9.9u         52%    -18.0u
rush_att              61%   +0.6pp        52%     -3.5u         50%    -15.6u
rush_yd               55%   +0.1pp        47%    -29.1u         45%    -44.5u
```

## Game markets (at the close)

```
games   n= 204  LL 0.6955 vs 0.6820  skill -0.020 z -1.1    level with the market (within noise)     beat close   30%  units   +0.1u
ml      n=  60  LL 0.6481 vs 0.6552  skill +0.011 z +0.3    level with the market (within noise)     beat close   42%  units   +8.5u
spread  n=  70  LL 0.7081 vs 0.6934  skill -0.021 z -0.8    level with the market (within noise)     beat close   29%  units   -7.0u
total   n=  74  LL 0.7221 vs 0.6929  skill -0.042 z -1.4    level with the market (within noise)     beat close   22%  units   -1.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 102  49.0% vs  49.5%           n= 112  49.1% vs  49.8%
no news                   n=1145  48.4% vs  49.5%           n=1250  48.7% vs  49.6%
usage down                n= 371  50.4% vs  49.1%           n= 423  50.3% vs  48.8%
usage up / teammate out   n=1400  49.5% vs  49.5%           n=1499  48.6% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 426  Vault's side won 223-203  skill -0.055 z -2.3
  agrees with the news     n= 269  Vault's side won 140-129  skill -0.009 z -0.3
  no news                  n= 452  Vault's side won 238-214  skill -0.045 z -1.9
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
props   FanDuel     n= 18  toward   8 / away   3  net share toward +0.28 ±0.23
props   DraftKings  n= 17  toward   8 / away   1  net share toward +0.41 ±0.22
        -> too few props (61 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=293  log-loss Kalshi 0.6837  books 0.6858
Vault vs Kalshi (10+ pts, Kalshi)  n=146  side won  64, price said   77.4  -> no edge yet (z -2.2)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=125  model lean won 66  overs hit 60  | would-be plays 4-5 -1.2u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     444       44-41 +2.2u     42-43 -4.8u        12-7 +4.3u      12-7 +3.3u
all     2085    266-229 +34.8u  257-238 +11.3u      44-35 +11.5u    45-34 +11.1u
log-loss at the open, same 2085 props: market 0.6847  live model 0.6945  anchored 0.6836
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          10-9         +2.5u           +3.5u        2/18
6-24 hours before         7-8         -0.8u           -1.0u        3/13
under 6 hours           17-12         +3.4u           +1.0u        6/23
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 462  LL 0.6917 vs 0.6769  skill -0.022 z -1.7     games n=  33  LL 0.6634 vs 0.6650  skill +0.002 z +0.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
