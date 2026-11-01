# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4272  LL 0.6991 vs 0.6861  skill -0.019 z -3.9    n=3917  LL 0.6987 vs 0.6855  skill -0.019 z -3.8    market better than Vault
pass_att      n= 149  LL 0.7072 vs 0.6890  skill -0.026 z -1.1    n= 152  LL 0.7083 vs 0.6956  skill -0.018 z -0.7    level with the market (within noise)
pass_cmp      n= 169  LL 0.7134 vs 0.6885  skill -0.036 z -1.8    n= 169  LL 0.7155 vs 0.6850  skill -0.044 z -2.1    level with the market (within noise)
pass_td       n= 204  LL 0.6436 vs 0.6606  skill +0.026 z +1.2    n= 207  LL 0.6541 vs 0.6717  skill +0.026 z +1.3    level with the market (within noise)
pass_yd       n= 175  LL 0.7262 vs 0.6925  skill -0.049 z -2.1    n= 174  LL 0.7259 vs 0.6935  skill -0.047 z -2.0    market better than Vault
rec           n=1275  LL 0.6869 vs 0.6776  skill -0.014 z -1.6    n=1295  LL 0.6884 vs 0.6765  skill -0.018 z -2.0    level with the market (within noise)
rec_yd        n=1313  LL 0.7031 vs 0.6894  skill -0.020 z -2.3    n=1019  LL 0.7012 vs 0.6892  skill -0.017 z -1.9    market better than Vault
rush_att      n= 510  LL 0.7053 vs 0.6972  skill -0.012 z -0.8    n= 496  LL 0.6946 vs 0.6921  skill -0.004 z -0.2    level with the market (within noise)
rush_yd       n= 477  LL 0.7205 vs 0.6944  skill -0.038 z -2.0    n= 405  LL 0.7309 vs 0.6969  skill -0.049 z -2.4    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             485             51%        54%   +1.2
pass_int        216             49%        50%   +0.4
pass_td          35             64%        66%   +0.2
rec             175             55%        60%   +1.5
rec_yd           41             40%        39%   -0.1
rush_yd          17             45%        47%   +0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -88.6u         52%   -171.6u
pass_att              63%   +0.2pp        57%    +12.0u         56%     +9.9u
pass_cmp              59%   +0.2pp        45%    -26.8u         46%    -21.2u
pass_td               51%   +0.1pp        61%    +10.1u         60%     +9.3u
pass_yd               57%   +0.1pp        49%    -13.9u         49%    -15.4u
rec                   59%   +0.2pp        58%    +48.7u         55%    +24.9u
rec_yd                56%   -0.1pp        52%    -30.2u         51%    -60.3u
rush_att              63%   +0.7pp        54%     +7.9u         51%    -13.2u
rush_yd               58%   +0.1pp        45%    -61.1u         45%    -70.3u
```

## Game markets (at the close)

```
games   n= 302  LL 0.7046 vs 0.6865  skill -0.026 z -1.9    level with the market (within noise)     beat close   27%  units  -15.8u
ml      n=  90  LL 0.6677 vs 0.6687  skill +0.002 z +0.1    level with the market (within noise)     beat close   42%  units   +9.1u
spread  n= 104  LL 0.7146 vs 0.6959  skill -0.027 z -1.4    level with the market (within noise)     beat close   23%  units  -20.0u
total   n= 108  LL 0.7256 vs 0.6923  skill -0.048 z -1.9    level with the market (within noise)     beat close   19%  units   -4.9u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 193  48.2% vs  49.3%           n= 218  47.2% vs  49.2%
no news                   n=1586  48.0% vs  49.3%           n=1741  48.0% vs  49.5%
usage down                n= 508  50.0% vs  49.3%           n= 580  49.8% vs  48.9%
usage up / teammate out   n=2318  50.1% vs  49.5%           n=2465  49.2% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 696  Vault's side won 353-343  skill -0.063 z -3.4
  agrees with the news     n= 394  Vault's side won 213-181  skill +0.001 z +0.0
  no news                  n= 606  Vault's side won 318-288  skill -0.029 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 76  toward  47 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 65  toward  37 / away  17  avg move toward +0.28 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 39  toward  24 / away  12  avg move toward +0.23 pts ±0.17
total   FanDuel     n= 40  toward  23 / away  12  avg move toward +0.15 pts ±0.17
        -> too few games (39 of 50)
props   Pinnacle    n=230  toward 120 / away  20  net share toward +0.43 ±0.06
props   FanDuel     n= 68  toward  41 / away   9  net share toward +0.47 ±0.11
props   DraftKings  n= 28  toward  10 / away   4  net share toward +0.21 ±0.18
        -> NO-GO: not ahead of the controls (-0.04, z -0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 33  side won  21, price said   16.3  -> tracking (33 of 50)
  all Kalshi-priced lines: n=904  log-loss Kalshi 0.684  books 0.6874
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=341  model lean won 172  overs hit 167  | would-be plays 6-10 -4.4u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     547       44-55 -9.8u     47-52 -7.0u         6-6 +0.7u       6-6 +1.2u
Wk 7     541       40-40 +1.4u     41-39 +1.6u         3-6 -2.5u       3-6 -2.4u
Wk 8     150        9-14 -2.8u      9-14 -3.7u         2-2 +0.4u       2-2 -0.1u
all     3445    372-354 +19.9u   368-358 -0.1u      57-50 +11.1u    58-49 +10.7u
log-loss at the open, same 3445 props: market 0.6845  live model 0.6955  anchored 0.6836
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           17-9         +7.7u           +6.3u       14/25
1-3 days before         17-14         +4.5u           +4.7u        7/30
6-24 hours before       10-12         -2.2u           -2.7u        7/20
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7235 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7177 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7010 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7660 vs 0.7216  skill -0.062 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7061 vs 0.6723  skill -0.050 z -1.2
Wk  8  props n= 170  LL 0.7004 vs 0.6869  skill -0.020 z -0.9     games n=  11  LL 0.6523 vs 0.6410  skill -0.018 z -0.3
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
