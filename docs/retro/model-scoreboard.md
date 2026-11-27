# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=6662  LL 0.7011 vs 0.6868  skill -0.021 z -5.5    n=6114  LL 0.7001 vs 0.6877  skill -0.018 z -4.7    market better than Vault
pass_att      n= 251  LL 0.7143 vs 0.6908  skill -0.034 z -2.0    n= 255  LL 0.7169 vs 0.6945  skill -0.032 z -1.8    level with the market (within noise)
pass_cmp      n= 270  LL 0.7045 vs 0.6892  skill -0.022 z -1.5    n= 269  LL 0.7074 vs 0.6858  skill -0.032 z -1.9    level with the market (within noise)
pass_td       n= 310  LL 0.6670 vs 0.6710  skill +0.006 z +0.4    n= 313  LL 0.6779 vs 0.6829  skill +0.007 z +0.5    level with the market (within noise)
pass_yd       n= 281  LL 0.7234 vs 0.6911  skill -0.047 z -2.7    n= 280  LL 0.7225 vs 0.6926  skill -0.043 z -2.5    market better than Vault
rec           n=1945  LL 0.6891 vs 0.6761  skill -0.019 z -2.8    n=1991  LL 0.6909 vs 0.6802  skill -0.016 z -2.3    market better than Vault
rec_yd        n=2016  LL 0.7009 vs 0.6922  skill -0.013 z -2.0    n=1568  LL 0.6994 vs 0.6920  skill -0.011 z -1.6    level with the market (within noise)
rush_att      n= 811  LL 0.7097 vs 0.6947  skill -0.022 z -2.0    n= 788  LL 0.6991 vs 0.6904  skill -0.013 z -1.1    level with the market (within noise)
rush_yd       n= 778  LL 0.7231 vs 0.6940  skill -0.042 z -2.9    n= 650  LL 0.7227 vs 0.6954  skill -0.039 z -2.5    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             742             52%        57%   +2.9
pass_int        323             49%        53%   +1.2
pass_td          51             63%        57%   -0.9
rec             272             55%        64%   +2.8
rec_yd           66             40%        52%   +1.8
rush_yd          28             45%        46%   +0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -197.8u         51%   -293.1u
pass_att              65%   +0.3pp        53%     +1.4u         52%     -0.5u
pass_cmp              61%   +0.2pp        48%    -28.7u         48%    -25.4u
pass_td               48%   -0.1pp        55%    -20.5u         54%    -22.6u
pass_yd               55%   +0.1pp        48%    -27.9u         48%    -29.2u
rec                   58%   +0.1pp        56%     +9.0u         54%     -6.1u
rec_yd                57%   -0.1pp        51%    -46.9u         51%    -67.8u
rush_att              61%   +0.5pp        52%    -16.1u         49%    -41.4u
rush_yd               60%   +0.1pp        49%    -54.0u         47%    -81.2u
```

## Game markets (at the close)

```
games   n= 455  LL 0.6918 vs 0.6712  skill -0.031 z -2.7    market better than Vault                 beat close   29%  units  -33.4u
ml      n= 133  LL 0.6317 vs 0.6173  skill -0.023 z -1.1    level with the market (within noise)     beat close   44%  units   -5.4u
spread  n= 159  LL 0.7183 vs 0.6944  skill -0.034 z -2.0    level with the market (within noise)     beat close   24%  units  -19.6u
total   n= 163  LL 0.7150 vs 0.6927  skill -0.032 z -1.6    level with the market (within noise)     beat close   20%  units   -8.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 322  45.0% vs  49.1%           n= 367  43.9% vs  49.1%
no news                   n=2560  50.0% vs  49.4%           n=2792  50.2% vs  49.4%
usage down                n= 846  48.8% vs  49.4%           n= 950  49.0% vs  49.1%
usage up / teammate out   n=3439  48.9% vs  49.6%           n=3680  48.4% vs  49.6%

Vault vs market disagreements of 8+ pts (close):
  against the news         n=1005  Vault's side won 504-501  skill -0.065 z -4.4
  agrees with the news     n= 588  Vault's side won 319-269  skill +0.000 z +0.0
  no news                  n= 936  Vault's side won 479-457  skill -0.039 z -2.6
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 89  toward  55 / away  21  avg move toward +0.36 pts ±0.10
spread  FanDuel     n= 92  toward  53 / away  27  avg move toward +0.18 pts ±0.13
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 46  toward  27 / away  16  avg move toward +0.21 pts ±0.15
total   FanDuel     n= 65  toward  39 / away  20  avg move toward +0.40 pts ±0.15
        -> too few games (46 of 50)
props   Pinnacle    n=322  toward 165 / away  25  net share toward +0.43 ±0.05
props   FanDuel     n= 97  toward  48 / away  11  net share toward +0.38 ±0.09
props   DraftKings  n= 45  toward  16 / away   8  net share toward +0.18 ±0.15
        -> NO-GO: not ahead of the controls (+0.05, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 49  side won  31, price said   24.1  -> tracking (49 of 50)
  all Kalshi-priced lines: n=1794  log-loss Kalshi 0.6839  books 0.6862
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 30  side won  21, price said   15.1  -> tracking (30 of 50)
PM sharp vs crowd disagree         n=  8  side won   5, price said    3.3  -> tracking (8 of 50)
PM sharp with crowd                n= 16  side won  12, price said    8.9  -> tracking (16 of 50)
Withheld props (teammate out)      lines=860  model lean won 445  overs hit 417  | would-be plays 7-11 -4.3u
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
Wk 9     554       56-46 +7.3u     58-44 +8.9u         5-2 +2.7u       5-2 +2.0u
Wk 10    564      63-45 +19.7u    62-46 +11.9u         0-2 -2.0u       0-2 -2.0u
Wk 11    553       58-66 -6.8u    56-68 -11.5u         6-5 -0.3u       5-6 -2.0u
Wk 12    126       17-11 +8.1u     17-11 +8.7u         0-1 -1.0u       0-1 -1.0u
all     5642    595-553 +45.9u  591-557 +15.5u       70-66 +6.2u     70-66 +3.8u
log-loss at the open, same 5642 props: market 0.6873  live model 0.6983  anchored 0.6868
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          19-13         +5.8u           +3.4u       17/30
1-3 days before         22-17         +6.6u           +6.4u       10/38
6-24 hours before       14-15         -1.1u           -2.0u       11/27
under 6 hours           24-14         +8.2u           +4.2u        8/31
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7268 vs 0.6807  skill -0.068 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7211 vs 0.6851  skill -0.053 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6656 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.6999 vs 0.6903  skill -0.014 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7693 vs 0.7216  skill -0.066 z -2.4
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7078 vs 0.6723  skill -0.053 z -1.3
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6599 vs 0.6433  skill -0.026 z -0.9
Wk  9  props n= 624  LL 0.6999 vs 0.6856  skill -0.021 z -1.9     games n=  42  LL 0.6493 vs 0.6208  skill -0.046 z -1.5
Wk 10  props n= 622  LL 0.7036 vs 0.6937  skill -0.014 z -1.3     games n=  41  LL 0.6278 vs 0.6524  skill +0.038 z +1.0
Wk 11  props n= 582  LL 0.7047 vs 0.6860  skill -0.027 z -2.5     games n=  35  LL 0.7124 vs 0.6423  skill -0.109 z -2.4
Wk 12  props n= 124  LL 0.6835 vs 0.6964  skill +0.018 z +0.8     games n=   8  LL 0.7168 vs 0.6747  skill -0.062 z -0.7
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
