# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=5816  LL 0.7008 vs 0.6863  skill -0.021 z -5.1    n=5303  LL 0.6998 vs 0.6867  skill -0.019 z -4.5    market better than Vault
pass_att      n= 220  LL 0.7113 vs 0.6893  skill -0.032 z -1.7    n= 222  LL 0.7135 vs 0.6933  skill -0.029 z -1.4    level with the market (within noise)
pass_cmp      n= 235  LL 0.7093 vs 0.6886  skill -0.030 z -1.8    n= 234  LL 0.7126 vs 0.6864  skill -0.038 z -2.1    level with the market (within noise)
pass_td       n= 275  LL 0.6645 vs 0.6699  skill +0.008 z +0.5    n= 277  LL 0.6761 vs 0.6815  skill +0.008 z +0.5    level with the market (within noise)
pass_yd       n= 245  LL 0.7274 vs 0.6910  skill -0.053 z -2.8    n= 244  LL 0.7270 vs 0.6926  skill -0.050 z -2.7    market better than Vault
rec           n=1706  LL 0.6884 vs 0.6751  skill -0.020 z -2.6    n=1739  LL 0.6906 vs 0.6787  skill -0.018 z -2.4    market better than Vault
rec_yd        n=1758  LL 0.7022 vs 0.6915  skill -0.015 z -2.2    n=1350  LL 0.6999 vs 0.6910  skill -0.013 z -1.8    market better than Vault
rush_att      n= 705  LL 0.7082 vs 0.6952  skill -0.019 z -1.6    n= 681  LL 0.6983 vs 0.6888  skill -0.014 z -1.1    level with the market (within noise)
rush_yd       n= 672  LL 0.7194 vs 0.6947  skill -0.036 z -2.2    n= 556  LL 0.7187 vs 0.6964  skill -0.032 z -1.9    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             637             52%        56%   +2.4
pass_int        287             49%        53%   +1.2
pass_td          46             64%        59%   -0.7
rec             226             55%        62%   +2.2
rec_yd           51             40%        47%   +1.0
rush_yd          25             45%        48%   +0.3
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -179.2u         51%   -274.2u
pass_att              66%   +0.3pp        53%     +3.5u         53%     +1.8u
pass_cmp              61%   +0.2pp        47%    -27.4u         47%    -24.4u
pass_td               47%   -0.1pp        56%    -14.9u         55%    -15.8u
pass_yd               56%   +0.1pp        47%    -31.3u         46%    -32.6u
rec                   59%   +0.1pp        56%     +1.7u         54%    -14.4u
rec_yd                56%   -0.1pp        51%    -45.2u         51%    -73.0u
rush_att              62%   +0.5pp        53%     -4.9u         50%    -32.3u
rush_yd               60%   +0.2pp        48%    -46.5u         48%    -62.3u
```

## Game markets (at the close)

```
games   n= 404  LL 0.6894 vs 0.6729  skill -0.025 z -2.1    market better than Vault                 beat close   29%  units  -20.0u
ml      n= 120  LL 0.6333 vs 0.6247  skill -0.014 z -0.6    level with the market (within noise)     beat close   46%  units   +0.6u
spread  n= 140  LL 0.7104 vs 0.6939  skill -0.024 z -1.3    level with the market (within noise)     beat close   25%  units  -15.9u
total   n= 144  LL 0.7159 vs 0.6925  skill -0.034 z -1.5    level with the market (within noise)     beat close   19%  units   -4.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 264  46.2% vs  49.2%           n= 305  45.6% vs  49.2%
no news                   n=2216  49.0% vs  49.4%           n=2438  49.3% vs  49.6%
usage down                n= 702  48.9% vs  49.3%           n= 806  48.9% vs  48.9%
usage up / teammate out   n=3029  49.4% vs  49.5%           n=3243  48.8% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 917  Vault's side won 462-455  skill -0.064 z -4.1
  agrees with the news     n= 520  Vault's side won 282-238  skill -0.001 z -0.1
  no news                  n= 828  Vault's side won 422-406  skill -0.040 z -2.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 89  toward  55 / away  21  avg move toward +0.36 pts ±0.10
spread  FanDuel     n= 82  toward  49 / away  22  avg move toward +0.25 pts ±0.14
        -> NO-GO: not ahead of the control (+0.11 pts, z +0.7)
total   Pinnacle    n= 46  toward  27 / away  16  avg move toward +0.21 pts ±0.15
total   FanDuel     n= 52  toward  32 / away  14  avg move toward +0.28 pts ±0.14
        -> too few games (46 of 50)
props   Pinnacle    n=269  toward 143 / away  21  net share toward +0.45 ±0.05
props   FanDuel     n= 86  toward  44 / away  11  net share toward +0.38 ±0.10
props   DraftKings  n= 41  toward  14 / away   7  net share toward +0.17 ±0.15
        -> NO-GO: not ahead of the controls (+0.07, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 46  side won  29, price said   22.7  -> tracking (46 of 50)
  all Kalshi-priced lines: n=1466  log-loss Kalshi 0.6833  books 0.6861
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 27  side won  20, price said   13.5  -> tracking (27 of 50)
PM sharp vs crowd disagree         n=  8  side won   5, price said    3.3  -> tracking (8 of 50)
PM sharp with crowd                n= 14  side won  11, price said    7.7  -> tracking (14 of 50)
Withheld props (teammate out)      lines=687  model lean won 355  overs hit 327  | would-be plays 6-10 -4.4u
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
Wk 10    432      50-31 +21.2u    50-31 +16.5u         0-2 -2.0u       0-2 -2.0u
all     4831    507-461 +47.1u  506-462 +23.9u       64-60 +7.6u     65-59 +6.8u
log-loss at the open, same 4831 props: market 0.6861  live model 0.6976  anchored 0.6857
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          18-11         +6.9u           +5.4u       16/28
1-3 days before         19-15         +5.5u           +5.8u        8/33
6-24 hours before       12-15         -3.3u           -3.9u       11/25
under 6 hours           23-13         +8.3u           +4.5u        8/29
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7266 vs 0.6807  skill -0.067 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7208 vs 0.6851  skill -0.052 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6656 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7000 vs 0.6903  skill -0.014 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7691 vs 0.7216  skill -0.066 z -2.4
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7077 vs 0.6723  skill -0.053 z -1.3
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6598 vs 0.6433  skill -0.026 z -0.9
Wk  9  props n= 624  LL 0.6999 vs 0.6856  skill -0.021 z -1.9     games n=  42  LL 0.6493 vs 0.6208  skill -0.046 z -1.5
Wk 10  props n= 482  LL 0.6997 vs 0.6905  skill -0.013 z -1.1     games n=  33  LL 0.6120 vs 0.6379  skill +0.041 z +0.9
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
