# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2412  LL 0.7022 vs 0.6881  skill -0.020 z -2.9    n=2188  LL 0.7017 vs 0.6876  skill -0.020 z -2.8    market better than Vault
pass_att      n=  72  LL 0.7197 vs 0.6878  skill -0.046 z -1.4    n=  73  LL 0.7243 vs 0.6911  skill -0.048 z -1.3    level with the market (within noise)
pass_cmp      n=  90  LL 0.7100 vs 0.6877  skill -0.032 z -1.3    n=  90  LL 0.7110 vs 0.6785  skill -0.048 z -1.8    level with the market (within noise)
pass_td       n= 126  LL 0.6396 vs 0.6685  skill +0.043 z +1.9    n= 125  LL 0.6573 vs 0.6822  skill +0.036 z +1.6    level with the market (within noise)
pass_yd       n=  91  LL 0.7091 vs 0.6925  skill -0.024 z -1.0    n=  91  LL 0.7146 vs 0.6920  skill -0.033 z -1.4    level with the market (within noise)
rec           n= 748  LL 0.6890 vs 0.6789  skill -0.015 z -1.2    n= 744  LL 0.6894 vs 0.6775  skill -0.018 z -1.4    level with the market (within noise)
rec_yd        n= 767  LL 0.7079 vs 0.6910  skill -0.024 z -1.9    n= 581  LL 0.7066 vs 0.6915  skill -0.022 z -1.6    level with the market (within noise)
rush_att      n= 278  LL 0.7232 vs 0.7067  skill -0.023 z -1.1    n= 270  LL 0.7055 vs 0.7020  skill -0.005 z -0.2    level with the market (within noise)
rush_yd       n= 240  LL 0.7227 vs 0.6952  skill -0.040 z -1.4    n= 214  LL 0.7347 vs 0.6982  skill -0.052 z -1.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             279             51%        55%   +1.3
pass_int        131             49%        51%   +0.5
pass_td          24             64%        71%   +0.7
rec              91             55%        59%   +0.8
rec_yd           23             38%        44%   +0.5
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -65.6u         51%   -119.7u
pass_att              69%   +0.2pp        56%     +4.6u         56%     +4.9u
pass_cmp              60%   +0.2pp        44%    -15.9u         46%    -12.7u
pass_td               53%   +0.2pp        59%     +2.9u         59%     +2.1u
pass_yd               60%   -0.0pp        41%    -20.3u         42%    -18.5u
rec                   59%   +0.1pp        58%    +30.3u         54%     +2.8u
rec_yd                55%   -0.1pp        52%     -4.5u         52%    -14.6u
rush_att              62%   +0.7pp        53%     -0.5u         50%    -12.2u
rush_yd               58%   +0.1pp        47%    -20.5u         45%    -36.4u
```

## Game markets (at the close)

```
games   n= 177  LL 0.7032 vs 0.6886  skill -0.021 z -1.1    level with the market (within noise)     beat close   30%  units   +0.6u
ml      n=  52  LL 0.6629 vs 0.6773  skill +0.021 z +0.5    level with the market (within noise)     beat close   40%  units  +11.1u
spread  n=  61  LL 0.7067 vs 0.6938  skill -0.019 z -0.6    level with the market (within noise)     beat close   30%  units   -5.6u
total   n=  64  LL 0.7326 vs 0.6928  skill -0.058 z -1.8    level with the market (within noise)     beat close   22%  units   -4.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 100  48.0% vs  49.4%           n= 110  48.2% vs  49.8%
no news                   n= 894  48.3% vs  49.5%           n= 997  48.8% vs  49.7%
usage down                n= 297  51.8% vs  48.9%           n= 341  50.4% vs  48.7%
usage up / teammate out   n=1291  50.2% vs  49.5%           n=1382  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 393  Vault's side won 201-192  skill -0.065 z -2.5
  agrees with the news     n= 236  Vault's side won 126-110  skill +0.002 z +0.1
  no news                  n= 382  Vault's side won 201-181  skill -0.044 z -1.6
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
Kalshi vs books (5+ pts apart)     n= 11  side won   6, price said    5.1  -> tracking (11 of 50)
  all Kalshi-priced lines: n=136  log-loss Kalshi 0.6969  books 0.6965
Vault vs Kalshi (10+ pts, Kalshi)  n= 83  side won  37, price said   44.2  -> no edge yet (z -1.6)
PM sharp $25k+ (all)               n= 20  side won  17, price said   10.3  -> tracking (20 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 11  side won   9, price said    6.2  -> tracking (11 of 50)
Withheld props (teammate out)      lines=110  model lean won 56  overs hit 54  | would-be plays 2-4 -2.2u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5      75        8-10 -2.1u      7-11 -4.5u         2-3 -1.0u       2-3 -1.2u
all     1716    230-198 +30.5u  222-206 +11.6u       34-31 +6.3u     35-30 +6.7u
log-loss at the open, same 1716 props: market 0.6862  live model 0.6960  anchored 0.6853
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-3         +4.8u           +4.0u        6/10
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         7-6         +1.2u           +1.0u        3/11
under 6 hours           16-12         +2.5u           +0.1u        6/22
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n=  79  LL 0.6854 vs 0.6607  skill -0.037 z -1.2     games n=   6  LL 0.7443 vs 0.7823  skill +0.049 z +0.6
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
