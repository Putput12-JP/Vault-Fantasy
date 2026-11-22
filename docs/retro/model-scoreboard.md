# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=6219  LL 0.7007 vs 0.6869  skill -0.020 z -5.1    n=5686  LL 0.6994 vs 0.6876  skill -0.017 z -4.3    market better than Vault
pass_att      n= 237  LL 0.7125 vs 0.6908  skill -0.031 z -1.7    n= 239  LL 0.7145 vs 0.6938  skill -0.030 z -1.6    level with the market (within noise)
pass_cmp      n= 253  LL 0.7041 vs 0.6885  skill -0.023 z -1.4    n= 252  LL 0.7068 vs 0.6848  skill -0.032 z -1.9    level with the market (within noise)
pass_td       n= 293  LL 0.6670 vs 0.6701  skill +0.005 z +0.3    n= 295  LL 0.6775 vs 0.6838  skill +0.009 z +0.6    level with the market (within noise)
pass_yd       n= 263  LL 0.7220 vs 0.6909  skill -0.045 z -2.5    n= 262  LL 0.7202 vs 0.6927  skill -0.040 z -2.3    market better than Vault
rec           n=1819  LL 0.6893 vs 0.6766  skill -0.019 z -2.6    n=1857  LL 0.6913 vs 0.6803  skill -0.016 z -2.3    market better than Vault
rec_yd        n=1879  LL 0.7010 vs 0.6920  skill -0.013 z -2.0    n=1453  LL 0.6990 vs 0.6915  skill -0.011 z -1.6    level with the market (within noise)
rush_att      n= 755  LL 0.7098 vs 0.6950  skill -0.021 z -1.9    n= 730  LL 0.6992 vs 0.6900  skill -0.013 z -1.1    level with the market (within noise)
rush_yd       n= 720  LL 0.7197 vs 0.6945  skill -0.036 z -2.4    n= 598  LL 0.7183 vs 0.6959  skill -0.032 z -2.0    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             689             52%        57%   +2.6
pass_int        305             49%        52%   +1.1
pass_td          50             63%        56%   -1.1
rec             249             55%        64%   +2.6
rec_yd           56             40%        52%   +1.7
rush_yd          27             45%        48%   +0.3
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        52%   -205.5u         51%   -295.7u
pass_att              66%   +0.3pp        53%     +2.0u         52%     +0.1u
pass_cmp              61%   +0.2pp        47%    -28.8u         47%    -25.6u
pass_td               47%   -0.1pp        55%    -20.3u         54%    -22.6u
pass_yd               55%   +0.1pp        47%    -32.3u         47%    -33.8u
rec                   59%   +0.1pp        56%     -0.9u         54%    -14.0u
rec_yd                56%   -0.1pp        52%    -44.0u         51%    -68.2u
rush_att              62%   +0.5pp        52%    -11.0u         50%    -34.7u
rush_yd               60%   +0.2pp        48%    -51.1u         47%    -76.4u
```

## Game markets (at the close)

```
games   n= 428  LL 0.6881 vs 0.6692  skill -0.028 z -2.4    market better than Vault                 beat close   28%  units  -27.8u
ml      n= 126  LL 0.6210 vs 0.6113  skill -0.016 z -0.7    level with the market (within noise)     beat close   44%  units   -2.6u
spread  n= 149  LL 0.7149 vs 0.6939  skill -0.030 z -1.6    level with the market (within noise)     beat close   24%  units  -15.4u
total   n= 153  LL 0.7172 vs 0.6929  skill -0.035 z -1.7    level with the market (within noise)     beat close   19%  units   -9.8u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 276  46.4% vs  49.2%           n= 320  45.3% vs  49.2%
no news                   n=2439  49.2% vs  49.4%           n=2665  49.3% vs  49.4%
usage down                n= 777  49.0% vs  49.3%           n= 880  49.3% vs  49.0%
usage up / teammate out   n=3178  48.9% vs  49.6%           n=3407  48.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 944  Vault's side won 474-470  skill -0.065 z -4.2
  agrees with the news     n= 548  Vault's side won 296-252  skill -0.000 z -0.0
  no news                  n= 904  Vault's side won 470-434  skill -0.034 z -2.2
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 89  toward  55 / away  21  avg move toward +0.36 pts ±0.10
spread  FanDuel     n= 86  toward  50 / away  24  avg move toward +0.23 pts ±0.13
        -> NO-GO: not ahead of the control (+0.13 pts, z +0.8)
total   Pinnacle    n= 46  toward  27 / away  16  avg move toward +0.21 pts ±0.15
total   FanDuel     n= 58  toward  35 / away  17  avg move toward +0.32 pts ±0.14
        -> too few games (46 of 50)
props   Pinnacle    n=303  toward 158 / away  24  net share toward +0.44 ±0.05
props   FanDuel     n= 90  toward  46 / away  11  net share toward +0.39 ±0.10
props   DraftKings  n= 43  toward  15 / away   7  net share toward +0.19 ±0.15
        -> NO-GO: not ahead of the controls (+0.05, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 48  side won  30, price said   23.6  -> tracking (48 of 50)
  all Kalshi-priced lines: n=1620  log-loss Kalshi 0.6855  books 0.6878
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 27  side won  20, price said   13.5  -> tracking (27 of 50)
PM sharp vs crowd disagree         n=  8  side won   5, price said    3.3  -> tracking (8 of 50)
PM sharp with crowd                n= 14  side won  11, price said    7.7  -> tracking (14 of 50)
Withheld props (teammate out)      lines=750  model lean won 390  overs hit 358  | would-be plays 6-10 -4.4u
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
Wk 8     550       38-45 -5.1u     39-44 -6.1u         4-8 -3.9u       4-8 -4.0u
Wk 9     554       56-45 +8.3u     58-43 +9.9u         5-2 +2.7u       5-2 +2.0u
Wk 10    564      63-45 +19.7u    62-46 +11.9u         0-2 -2.0u       0-2 -2.0u
Wk 11    251       30-21 +9.3u     28-23 +4.9u         4-2 +1.5u       3-3 -0.0u
all     5214    550-496 +54.9u  546-500 +24.3u       68-62 +9.1u     68-62 +6.8u
log-loss at the open, same 5214 props: market 0.6871  live model 0.6974  anchored 0.6865
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          18-13         +4.9u           +3.4u       17/30
1-3 days before         22-15         +8.6u           +8.4u        9/36
6-24 hours before       13-15         -2.2u           -3.1u       11/26
under 6 hours           23-14         +7.3u           +3.5u        8/30
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7275 vs 0.6807  skill -0.069 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7218 vs 0.6851  skill -0.054 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6656 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.6998 vs 0.6903  skill -0.014 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7700 vs 0.7216  skill -0.067 z -2.4
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7082 vs 0.6723  skill -0.053 z -1.3
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6601 vs 0.6433  skill -0.026 z -0.9
Wk  9  props n= 624  LL 0.6999 vs 0.6856  skill -0.021 z -1.9     games n=  42  LL 0.6494 vs 0.6208  skill -0.046 z -1.5
Wk 10  props n= 622  LL 0.7036 vs 0.6937  skill -0.014 z -1.3     games n=  41  LL 0.6276 vs 0.6524  skill +0.038 z +1.0
Wk 11  props n= 263  LL 0.6897 vs 0.6910  skill +0.002 z +0.1     games n=  16  LL 0.6425 vs 0.5557  skill -0.156 z -2.0
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
