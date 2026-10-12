# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2859  LL 0.7006 vs 0.6869  skill -0.020 z -3.2    n=2615  LL 0.6998 vs 0.6861  skill -0.020 z -3.1    market better than Vault
pass_att      n=  91  LL 0.7097 vs 0.6877  skill -0.032 z -1.1    n=  92  LL 0.7100 vs 0.6911  skill -0.027 z -0.8    level with the market (within noise)
pass_cmp      n= 109  LL 0.7136 vs 0.6887  skill -0.036 z -1.5    n= 109  LL 0.7154 vs 0.6811  skill -0.050 z -1.9    level with the market (within noise)
pass_td       n= 147  LL 0.6402 vs 0.6683  skill +0.042 z +1.9    n= 148  LL 0.6526 vs 0.6776  skill +0.037 z +1.7    level with the market (within noise)
pass_yd       n= 114  LL 0.7291 vs 0.6940  skill -0.051 z -2.0    n= 114  LL 0.7335 vs 0.6925  skill -0.059 z -2.3    market better than Vault
rec           n= 872  LL 0.6886 vs 0.6776  skill -0.016 z -1.4    n= 872  LL 0.6886 vs 0.6759  skill -0.019 z -1.7    level with the market (within noise)
rec_yd        n= 893  LL 0.7046 vs 0.6895  skill -0.022 z -1.9    n= 685  LL 0.7020 vs 0.6907  skill -0.016 z -1.4    level with the market (within noise)
rush_att      n= 332  LL 0.7195 vs 0.7027  skill -0.024 z -1.3    n= 326  LL 0.7055 vs 0.6961  skill -0.013 z -0.7    level with the market (within noise)
rush_yd       n= 301  LL 0.7135 vs 0.6938  skill -0.028 z -1.2    n= 269  LL 0.7256 vs 0.6975  skill -0.040 z -1.6    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             318             51%        56%   +1.6
pass_int        154             49%        49%   -0.1
pass_td          26             64%        69%   +0.6
rec             102             56%        64%   +1.7
rec_yd           25             39%        48%   +1.0
rush_yd          11             45%        64%   +1.3
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -88.7u         51%   -137.7u
pass_att              66%   +0.1pp        58%     +8.4u         58%     +8.8u
pass_cmp              60%   +0.1pp        44%    -19.9u         45%    -16.3u
pass_td               53%   +0.1pp        60%     +6.4u         60%     +6.7u
pass_yd               58%   +0.2pp        42%    -24.7u         43%    -23.4u
rec                   58%   +0.1pp        58%    +34.2u         54%     +8.1u
rec_yd                56%   -0.1pp        53%     -6.0u         52%    -14.2u
rush_att              61%   +0.6pp        51%    -10.5u         49%    -22.4u
rush_yd               54%   +0.1pp        47%    -28.6u         46%    -41.3u
```

## Game markets (at the close)

```
games   n= 210  LL 0.6961 vs 0.6844  skill -0.017 z -1.0    level with the market (within noise)     beat close   30%  units   +0.4u
ml      n=  62  LL 0.6550 vs 0.6642  skill +0.014 z +0.4    level with the market (within noise)     beat close   42%  units   +9.0u
spread  n=  72  LL 0.7068 vs 0.6931  skill -0.020 z -0.8    level with the market (within noise)     beat close   28%  units   -7.1u
total   n=  76  LL 0.7194 vs 0.6926  skill -0.039 z -1.3    level with the market (within noise)     beat close   21%  units   -1.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 102  49.0% vs  49.5%           n= 112  49.1% vs  49.8%
no news                   n=1190  49.0% vs  49.6%           n=1300  49.2% vs  49.6%
usage down                n= 378  51.1% vs  49.1%           n= 432  50.9% vs  48.8%
usage up / teammate out   n=1416  49.6% vs  49.5%           n=1516  48.5% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 433  Vault's side won 227-206  skill -0.053 z -2.2
  agrees with the news     n= 271  Vault's side won 141-130  skill -0.009 z -0.3
  no news                  n= 466  Vault's side won 244-222  skill -0.047 z -2.0
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
props   DraftKings  n= 18  toward   8 / away   1  net share toward +0.39 ±0.22
        -> too few props (61 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=321  log-loss Kalshi 0.6823  books 0.6843
Vault vs Kalshi (10+ pts, Kalshi)  n=155  side won  67, price said   82.0  -> no edge yet (z -2.4)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=151  model lean won 80  overs hit 80  | would-be plays 5-8 -3.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     502       49-46 +1.6u     48-47 -3.7u        12-8 +3.3u      12-8 +2.3u
all     2143    271-234 +34.2u  263-242 +12.4u      44-36 +10.5u    45-35 +10.1u
log-loss at the open, same 2143 props: market 0.6847  live model 0.6949  anchored 0.6839
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          11-9         +3.8u           +4.7u        2/19
6-24 hours before         7-9         -1.8u           -2.0u        3/14
under 6 hours           19-12         +5.4u           +2.0u        6/24
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 526  LL 0.6908 vs 0.6771  skill -0.020 z -1.7     games n=  39  LL 0.6712 vs 0.6804  skill +0.013 z +0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
