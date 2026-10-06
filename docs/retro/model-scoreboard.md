# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2334  LL 0.7026 vs 0.6890  skill -0.020 z -2.7    n=2114  LL 0.7012 vs 0.6884  skill -0.019 z -2.5    market better than Vault
pass_att      n=  68  LL 0.7126 vs 0.6864  skill -0.038 z -1.1    n=  69  LL 0.7187 vs 0.6925  skill -0.038 z -1.0    level with the market (within noise)
pass_cmp      n=  86  LL 0.7044 vs 0.6893  skill -0.022 z -0.8    n=  86  LL 0.7068 vs 0.6797  skill -0.040 z -1.4    level with the market (within noise)
pass_td       n= 122  LL 0.6445 vs 0.6737  skill +0.043 z +1.8    n= 121  LL 0.6628 vs 0.6886  skill +0.038 z +1.6    level with the market (within noise)
pass_yd       n=  87  LL 0.7092 vs 0.6933  skill -0.023 z -1.0    n=  87  LL 0.7146 vs 0.6926  skill -0.032 z -1.3    level with the market (within noise)
rec           n= 727  LL 0.6892 vs 0.6788  skill -0.015 z -1.2    n= 722  LL 0.6895 vs 0.6781  skill -0.017 z -1.3    level with the market (within noise)
rec_yd        n= 748  LL 0.7079 vs 0.6922  skill -0.023 z -1.8    n= 564  LL 0.7063 vs 0.6917  skill -0.021 z -1.5    level with the market (within noise)
rush_att      n= 267  LL 0.7232 vs 0.7081  skill -0.021 z -1.0    n= 259  LL 0.7057 vs 0.7024  skill -0.005 z -0.2    level with the market (within noise)
rush_yd       n= 229  LL 0.7278 vs 0.6959  skill -0.046 z -1.6    n= 206  LL 0.7316 vs 0.6984  skill -0.048 z -1.6    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             268             51%        56%   +1.4
pass_int        127             49%        51%   +0.5
pass_td          22             64%        68%   +0.5
rec              88             56%        60%   +0.8
rec_yd           21             38%        48%   +0.9
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -67.8u         51%   -123.2u
pass_att              67%   +0.2pp        57%     +5.0u         57%     +5.0u
pass_cmp              62%   +0.2pp        47%    -11.9u         48%     -8.7u
pass_td               54%   +0.2pp        58%     +2.5u         58%     +1.5u
pass_yd               64%   -0.0pp        40%    -21.9u         41%    -20.0u
rec                   59%   +0.1pp        58%    +26.4u         54%     -1.6u
rec_yd                55%   -0.0pp        52%     -6.5u         52%    -16.0u
rush_att              62%   +0.6pp        53%     +0.9u         50%    -10.5u
rush_yd               59%   +0.1pp        47%    -20.1u         44%    -37.4u
```

## Game markets (at the close)

```
games   n= 171  LL 0.7016 vs 0.6853  skill -0.024 z -1.2    level with the market (within noise)     beat close   30%  units   -1.8u
ml      n=  50  LL 0.6560 vs 0.6667  skill +0.016 z +0.4    level with the market (within noise)     beat close   42%  units   +8.4u
spread  n=  59  LL 0.7095 vs 0.6938  skill -0.022 z -0.8    level with the market (within noise)     beat close   31%  units   -7.5u
total   n=  62  LL 0.7308 vs 0.6922  skill -0.056 z -1.7    level with the market (within noise)     beat close   21%  units   -2.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  93  49.5% vs  49.5%           n= 103  49.5% vs  49.9%
no news                   n= 871  47.0% vs  49.4%           n= 968  47.6% vs  49.7%
usage down                n= 296  51.0% vs  48.8%           n= 341  49.9% vs  48.6%
usage up / teammate out   n=1236  50.6% vs  49.5%           n=1329  49.7% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 385  Vault's side won 196-189  skill -0.069 z -2.7
  agrees with the news     n= 232  Vault's side won 123-109  skill +0.000 z +0.0
  no news                  n= 368  Vault's side won 197-171  skill -0.035 z -1.3
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
Kalshi vs books (5+ pts apart)     n= 13  side won   8, price said    6.1  -> tracking (13 of 50)
  all Kalshi-priced lines: n=221  log-loss Kalshi 0.6914  books 0.697
Vault vs Kalshi (10+ pts, Kalshi)  n=176  side won  77, price said   91.0  -> no edge yet (z -2.1)
PM sharp $25k+ (all)               n= 20  side won  17, price said   10.3  -> tracking (20 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 11  side won   9, price said    6.2  -> tracking (11 of 50)
Withheld props (teammate out)      lines=105  model lean won 54  overs hit 53  | would-be plays 0-3 -3.0u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     636      72-64 +10.0u     71-65 +4.8u       10-10 +0.7u     10-10 +0.8u
all     1642    222-187 +33.6u  215-194 +17.1u       32-28 +7.3u     33-27 +7.8u
log-loss at the open, same 1642 props: market 0.6872  live model 0.6952  anchored 0.6859
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-3         +4.8u           +4.0u        6/10
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         7-6         +1.2u           +1.0u        3/11
under 6 hours           15-11         +2.4u           +0.2u        5/20
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 677  LL 0.7072 vs 0.6948  skill -0.018 z -1.7     games n=  44  LL 0.7010 vs 0.6903  skill -0.015 z -0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
