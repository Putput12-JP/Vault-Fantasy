# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2374  LL 0.7017 vs 0.6882  skill -0.020 z -2.8    n=2150  LL 0.7008 vs 0.6877  skill -0.019 z -2.6    market better than Vault
pass_att      n=  70  LL 0.7132 vs 0.6863  skill -0.039 z -1.2    n=  71  LL 0.7191 vs 0.6919  skill -0.039 z -1.1    level with the market (within noise)
pass_cmp      n=  88  LL 0.7074 vs 0.6886  skill -0.027 z -1.1    n=  88  LL 0.7084 vs 0.6792  skill -0.043 z -1.6    level with the market (within noise)
pass_td       n= 124  LL 0.6396 vs 0.6700  skill +0.045 z +1.9    n= 123  LL 0.6575 vs 0.6841  skill +0.039 z +1.7    level with the market (within noise)
pass_yd       n=  89  LL 0.7087 vs 0.6931  skill -0.022 z -0.9    n=  89  LL 0.7134 vs 0.6919  skill -0.031 z -1.3    level with the market (within noise)
rec           n= 738  LL 0.6885 vs 0.6779  skill -0.016 z -1.2    n= 733  LL 0.6888 vs 0.6772  skill -0.017 z -1.3    level with the market (within noise)
rec_yd        n= 756  LL 0.7079 vs 0.6914  skill -0.024 z -1.9    n= 570  LL 0.7066 vs 0.6917  skill -0.021 z -1.6    level with the market (within noise)
rush_att      n= 273  LL 0.7212 vs 0.7080  skill -0.019 z -0.9    n= 265  LL 0.7031 vs 0.7018  skill -0.002 z -0.1    level with the market (within noise)
rush_yd       n= 236  LL 0.7254 vs 0.6950  skill -0.044 z -1.5    n= 211  LL 0.7348 vs 0.6982  skill -0.052 z -1.7    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             272             51%        56%   +1.4
pass_int        129             49%        51%   +0.5
pass_td          23             64%        70%   +0.6
rec              89             56%        60%   +0.8
rec_yd           21             38%        48%   +0.9
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -62.5u         51%   -117.8u
pass_att              68%   +0.2pp        56%     +4.8u         56%     +4.9u
pass_cmp              60%   +0.2pp        45%    -13.9u         47%    -10.7u
pass_td               54%   +0.2pp        59%     +3.4u         59%     +2.6u
pass_yd               62%   -0.0pp        40%    -22.1u         41%    -20.3u
rec                   59%   +0.1pp        58%    +31.1u         54%     +3.3u
rec_yd                55%   -0.0pp        52%     -4.8u         52%    -15.9u
rush_att              62%   +0.7pp        53%     +2.6u         50%     -9.0u
rush_yd               59%   +0.1pp        47%    -21.3u         45%    -37.0u
```

## Game markets (at the close)

```
games   n= 174  LL 0.7056 vs 0.6909  skill -0.021 z -1.1    level with the market (within noise)     beat close   30%  units   +1.7u
ml      n=  51  LL 0.6684 vs 0.6852  skill +0.025 z +0.6    level with the market (within noise)     beat close   41%  units  +12.1u
spread  n=  60  LL 0.7092 vs 0.6938  skill -0.022 z -0.7    level with the market (within noise)     beat close   30%  units   -6.5u
total   n=  63  LL 0.7323 vs 0.6927  skill -0.057 z -1.7    level with the market (within noise)     beat close   22%  units   -3.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  98  49.0% vs  49.3%           n= 108  49.1% vs  49.7%
no news                   n= 866  47.6% vs  49.4%           n= 968  48.1% vs  49.7%
usage down                n= 293  51.5% vs  48.9%           n= 338  50.3% vs  48.7%
usage up / teammate out   n=1281  50.2% vs  49.5%           n=1373  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 392  Vault's side won 201-191  skill -0.064 z -2.5
  agrees with the news     n= 233  Vault's side won 124-109  skill +0.001 z +0.0
  no news                  n= 374  Vault's side won 198-176  skill -0.041 z -1.5
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
props   Pinnacle    n= 40  toward  14 / away   6  net share toward +0.20 ±0.15
props   FanDuel     n= 12  toward   3 / away   2  net share toward +0.08 ±0.29
props   DraftKings  n=  7  toward   3 / away   0  net share toward +0.43 ±0.34
        -> too few props (40 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 11  side won   6, price said    5.1  -> tracking (11 of 50)
  all Kalshi-priced lines: n=120  log-loss Kalshi 0.6975  books 0.6979
Vault vs Kalshi (10+ pts, Kalshi)  n= 77  side won  36, price said   41.2  -> no edge yet (z -1.2)
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
Wk 5      37         4-4 -0.2u       3-5 -2.4u         2-1 +1.0u       2-1 +0.8u
all     1678    226-192 +32.4u  218-200 +13.6u       34-29 +8.3u     35-28 +8.7u
log-loss at the open, same 1678 props: market 0.6863  live model 0.6948  anchored 0.6850
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-3         +4.8u           +4.0u        6/10
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         7-6         +1.2u           +1.0u        3/11
under 6 hours           15-12         +1.4u           -0.8u        6/21
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7249 vs 0.6807  skill -0.065 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7191 vs 0.6851  skill -0.050 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6656 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7005 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n=  41  LL 0.6431 vs 0.6366  skill -0.010 z -0.2     games n=   3  LL 0.8995 vs 1.0095  skill +0.109 z +1.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
