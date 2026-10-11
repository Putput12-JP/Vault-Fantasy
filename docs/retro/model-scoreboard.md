# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2830  LL 0.7004 vs 0.6871  skill -0.019 z -3.1    n=2589  LL 0.6994 vs 0.6859  skill -0.020 z -3.0    market better than Vault
pass_att      n=  90  LL 0.7096 vs 0.6873  skill -0.033 z -1.1    n=  91  LL 0.7119 vs 0.6915  skill -0.029 z -0.9    level with the market (within noise)
pass_cmp      n= 108  LL 0.7155 vs 0.6892  skill -0.038 z -1.6    n= 108  LL 0.7182 vs 0.6811  skill -0.054 z -2.1    level with the market (within noise)
pass_td       n= 146  LL 0.6311 vs 0.6649  skill +0.051 z +2.4    n= 147  LL 0.6436 vs 0.6744  skill +0.046 z +2.2    Vault better than the market
pass_yd       n= 113  LL 0.7277 vs 0.6940  skill -0.049 z -1.9    n= 113  LL 0.7322 vs 0.6925  skill -0.057 z -2.3    level with the market (within noise)
rec           n= 863  LL 0.6890 vs 0.6787  skill -0.015 z -1.3    n= 863  LL 0.6885 vs 0.6759  skill -0.019 z -1.6    level with the market (within noise)
rec_yd        n= 884  LL 0.7050 vs 0.6895  skill -0.022 z -2.0    n= 677  LL 0.7023 vs 0.6907  skill -0.017 z -1.4    level with the market (within noise)
rush_att      n= 329  LL 0.7187 vs 0.7024  skill -0.023 z -1.3    n= 323  LL 0.7043 vs 0.6959  skill -0.012 z -0.7    level with the market (within noise)
rush_yd       n= 297  LL 0.7153 vs 0.6945  skill -0.030 z -1.2    n= 267  LL 0.7261 vs 0.6975  skill -0.041 z -1.6    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             316             51%        56%   +1.6
pass_int        153             49%        49%   +0.0
pass_td          26             64%        69%   +0.6
rec             101             55%        63%   +1.6
rec_yd           25             39%        48%   +1.0
rush_yd          11             45%        64%   +1.3
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -89.0u         51%   -136.6u
pass_att              65%   +0.1pp        57%     +7.6u         57%     +7.8u
pass_cmp              60%   +0.1pp        44%    -20.7u         44%    -17.1u
pass_td               53%   +0.1pp        61%     +7.4u         61%     +7.7u
pass_yd               58%   +0.2pp        42%    -23.7u         43%    -22.4u
rec                   58%   +0.1pp        58%    +32.9u         54%     +6.8u
rec_yd                56%   -0.1pp        52%     -7.5u         52%    -14.5u
rush_att              61%   +0.6pp        51%     -9.5u         49%    -21.6u
rush_yd               54%   +0.1pp        47%    -28.5u         46%    -40.8u
```

## Game markets (at the close)

```
games   n= 207  LL 0.6979 vs 0.6834  skill -0.021 z -1.2    level with the market (within noise)     beat close   29%  units   -2.9u
ml      n=  61  LL 0.6547 vs 0.6596  skill +0.007 z +0.2    level with the market (within noise)     beat close   41%  units   +7.5u
spread  n=  71  LL 0.7098 vs 0.6938  skill -0.023 z -0.9    level with the market (within noise)     beat close   28%  units   -8.0u
total   n=  75  LL 0.7218 vs 0.6929  skill -0.042 z -1.4    level with the market (within noise)     beat close   21%  units   -2.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 102  49.0% vs  49.5%           n= 112  49.1% vs  49.8%
no news                   n=1168  48.5% vs  49.6%           n=1277  48.8% vs  49.6%
usage down                n= 373  50.4% vs  49.1%           n= 425  50.3% vs  48.8%
usage up / teammate out   n=1412  49.5% vs  49.5%           n=1512  48.5% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 431  Vault's side won 226-205  skill -0.054 z -2.2
  agrees with the news     n= 270  Vault's side won 141-129  skill -0.008 z -0.3
  no news                  n= 458  Vault's side won 242-216  skill -0.043 z -1.8
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
  all Kalshi-priced lines: n=308  log-loss Kalshi 0.6828  books 0.6846
Vault vs Kalshi (10+ pts, Kalshi)  n=150  side won  64, price said   79.3  -> no edge yet (z -2.5)
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
Wk 5     476       48-42 +4.7u     47-43 -0.6u        12-7 +4.3u      12-7 +3.3u
all     2117    270-230 +37.3u  262-238 +15.5u      44-35 +11.5u    45-34 +11.1u
log-loss at the open, same 2117 props: market 0.6844  live model 0.6943  anchored 0.6834
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          11-9         +3.8u           +4.7u        2/19
6-24 hours before         7-8         -0.8u           -1.0u        3/13
under 6 hours           18-12         +4.4u           +2.0u        6/24
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 497  LL 0.6894 vs 0.6777  skill -0.017 z -1.4     games n=  36  LL 0.6796 vs 0.6743  skill -0.008 z -0.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
