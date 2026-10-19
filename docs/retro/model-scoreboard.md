# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3440  LL 0.7024 vs 0.6868  skill -0.023 z -4.0    n=3156  LL 0.7025 vs 0.6866  skill -0.023 z -4.0    market better than Vault
pass_att      n= 115  LL 0.7173 vs 0.6885  skill -0.042 z -1.5    n= 117  LL 0.7208 vs 0.6933  skill -0.040 z -1.3    level with the market (within noise)
pass_cmp      n= 135  LL 0.7229 vs 0.6895  skill -0.048 z -2.1    n= 136  LL 0.7235 vs 0.6852  skill -0.056 z -2.4    market better than Vault
pass_td       n= 172  LL 0.6399 vs 0.6684  skill +0.043 z +2.0    n= 173  LL 0.6528 vs 0.6778  skill +0.037 z +1.8    Vault better than the market
pass_yd       n= 141  LL 0.7334 vs 0.6920  skill -0.060 z -2.4    n= 141  LL 0.7331 vs 0.6921  skill -0.059 z -2.4    market better than Vault
rec           n=1035  LL 0.6897 vs 0.6781  skill -0.017 z -1.7    n=1050  LL 0.6919 vs 0.6762  skill -0.023 z -2.3    level with the market (within noise)
rec_yd        n=1064  LL 0.7077 vs 0.6899  skill -0.026 z -2.6    n= 816  LL 0.7044 vs 0.6907  skill -0.020 z -1.9    market better than Vault
rush_att      n= 403  LL 0.7148 vs 0.6998  skill -0.021 z -1.3    n= 394  LL 0.6993 vs 0.6958  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 375  LL 0.7145 vs 0.6928  skill -0.031 z -1.4    n= 329  LL 0.7332 vs 0.6986  skill -0.050 z -2.1    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             378             52%        56%   +1.9
pass_int        181             49%        50%   +0.3
pass_td          30             64%        70%   +0.7
rec             126             55%        64%   +2.0
rec_yd           28             39%        46%   +0.8
rush_yd          13             45%        54%   +0.6
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        52%   -126.1u         51%   -187.9u
pass_att              64%   +0.1pp        56%     +8.3u         56%     +8.6u
pass_cmp              62%   +0.2pp        44%    -24.0u         45%    -20.1u
pass_td               52%   +0.1pp        59%     +4.6u         59%     +5.1u
pass_yd               59%   +0.2pp        44%    -24.3u         45%    -22.9u
rec                   58%   +0.2pp        57%    +28.2u         54%     +3.5u
rec_yd                56%   -0.1pp        52%    -16.4u         51%    -38.1u
rush_att              61%   +0.6pp        52%     -3.1u         50%    -18.3u
rush_yd               56%   +0.1pp        47%    -38.7u         46%    -49.0u
```

## Game markets (at the close)

```
games   n= 248  LL 0.7070 vs 0.6909  skill -0.023 z -1.5    level with the market (within noise)     beat close   29%  units  -12.6u
ml      n=  74  LL 0.6770 vs 0.6852  skill +0.012 z +0.4    level with the market (within noise)     beat close   45%  units  +10.6u
spread  n=  85  LL 0.7138 vs 0.6944  skill -0.028 z -1.2    level with the market (within noise)     beat close   26%  units  -14.4u
total   n=  89  LL 0.7254 vs 0.6924  skill -0.048 z -1.8    level with the market (within noise)     beat close   19%  units   -8.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 130  48.5% vs  49.5%           n= 144  47.9% vs  49.4%
no news                   n=1400  49.0% vs  49.5%           n=1528  48.8% vs  49.7%
usage down                n= 443  51.5% vs  49.2%           n= 509  50.9% vs  48.9%
usage up / teammate out   n=1746  50.2% vs  49.5%           n=1860  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 534  Vault's side won 277-257  skill -0.058 z -2.7
  agrees with the news     n= 323  Vault's side won 172-151  skill -0.002 z -0.1
  no news                  n= 541  Vault's side won 269-272  skill -0.058 z -2.7
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 61  toward  36 / away  14  avg move toward +0.46 pts ±0.11
spread  FanDuel     n= 50  toward  25 / away  14  avg move toward +0.18 pts ±0.15
        -> NO-GO: not ahead of the control (+0.28 pts, z +1.5)
total   Pinnacle    n= 30  toward  21 / away   8  avg move toward +0.41 pts ±0.19
total   FanDuel     n= 36  toward  21 / away  10  avg move toward +0.10 pts ±0.16
        -> too few games (30 of 50)
props   Pinnacle    n=128  toward  65 / away  10  net share toward +0.43 ±0.08
props   FanDuel     n= 35  toward  16 / away   7  net share toward +0.26 ±0.16
props   DraftKings  n= 23  toward  10 / away   3  net share toward +0.30 ±0.20
        -> NO-GO: not ahead of the controls (+0.13, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 17  side won   9, price said    8.0  -> tracking (17 of 50)
  all Kalshi-priced lines: n=563  log-loss Kalshi 0.6873  books 0.6879
Vault vs Kalshi (10+ pts, Kalshi)  n=164  side won  74, price said   87.0  -> no edge yet (z -2.1)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=215  model lean won 105  overs hit 109  | would-be plays 5-9 -4.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     477      39-50 -10.4u     42-47 -7.2u         5-5 -0.0u       5-5 +0.4u
all     2684    318-295 +20.7u   313-300 +1.9u      51-41 +12.5u    52-40 +12.4u
log-loss at the open, same 2684 props: market 0.6855  live model 0.6990  anchored 0.6851
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           13-9         +3.9u           +2.9u       12/21
1-3 days before         13-10         +4.8u           +5.5u        3/22
6-24 hours before        9-10         -0.8u           -1.2u        5/17
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7250 vs 0.6807  skill -0.065 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7192 vs 0.6851  skill -0.050 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7005 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 510  LL 0.7104 vs 0.6849  skill -0.037 z -2.8     games n=  35  LL 0.7691 vs 0.7241  skill -0.062 z -2.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
