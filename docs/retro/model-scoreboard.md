# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=5737  LL 0.7008 vs 0.6860  skill -0.022 z -5.2    n=5229  LL 0.6999 vs 0.6864  skill -0.020 z -4.6    market better than Vault
pass_att      n= 216  LL 0.7106 vs 0.6893  skill -0.031 z -1.6    n= 218  LL 0.7132 vs 0.6931  skill -0.029 z -1.4    level with the market (within noise)
pass_cmp      n= 231  LL 0.7080 vs 0.6875  skill -0.030 z -1.8    n= 230  LL 0.7122 vs 0.6853  skill -0.039 z -2.2    level with the market (within noise)
pass_td       n= 271  LL 0.6618 vs 0.6666  skill +0.007 z +0.4    n= 273  LL 0.6735 vs 0.6781  skill +0.007 z +0.4    level with the market (within noise)
pass_yd       n= 241  LL 0.7302 vs 0.6909  skill -0.057 z -3.0    n= 240  LL 0.7300 vs 0.6926  skill -0.054 z -2.9    market better than Vault
rec           n=1686  LL 0.6884 vs 0.6749  skill -0.020 z -2.7    n=1716  LL 0.6908 vs 0.6783  skill -0.018 z -2.5    market better than Vault
rec_yd        n=1735  LL 0.7027 vs 0.6915  skill -0.016 z -2.3    n=1331  LL 0.7005 vs 0.6909  skill -0.014 z -1.9    market better than Vault
rush_att      n= 695  LL 0.7081 vs 0.6954  skill -0.018 z -1.5    n= 672  LL 0.6978 vs 0.6894  skill -0.012 z -1.0    level with the market (within noise)
rush_yd       n= 662  LL 0.7194 vs 0.6949  skill -0.035 z -2.2    n= 549  LL 0.7191 vs 0.6966  skill -0.032 z -1.9    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             629             52%        56%   +2.5
pass_int        283             49%        53%   +1.3
pass_td          44             64%        61%   -0.4
rec             225             55%        62%   +2.2
rec_yd           51             40%        47%   +1.0
rush_yd          24             45%        50%   +0.5
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -180.7u         51%   -281.4u
pass_att              65%   +0.3pp        53%     +3.7u         53%     +2.0u
pass_cmp              61%   +0.2pp        47%    -27.5u         47%    -24.5u
pass_td               48%   -0.1pp        56%    -12.8u         56%    -13.9u
pass_yd               57%   +0.1pp        46%    -33.0u         46%    -34.1u
rec                   58%   +0.1pp        56%     +2.8u         54%    -13.7u
rec_yd                56%   -0.1pp        51%    -42.9u         51%    -72.7u
rush_att              62%   +0.5pp        53%     -5.0u         50%    -33.9u
rush_yd               60%   +0.2pp        48%    -48.9u         48%    -65.4u
```

## Game markets (at the close)

```
games   n= 398  LL 0.6911 vs 0.6747  skill -0.024 z -2.0    market better than Vault                 beat close   29%  units  -15.9u
ml      n= 118  LL 0.6382 vs 0.6306  skill -0.012 z -0.5    level with the market (within noise)     beat close   47%  units   +2.6u
spread  n= 138  LL 0.7092 vs 0.6941  skill -0.022 z -1.2    level with the market (within noise)     beat close   25%  units  -13.9u
total   n= 142  LL 0.7174 vs 0.6925  skill -0.036 z -1.7    level with the market (within noise)     beat close   19%  units   -4.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 264  46.2% vs  49.2%           n= 305  45.6% vs  49.2%
no news                   n=2156  49.2% vs  49.4%           n=2376  49.4% vs  49.5%
usage down                n= 691  49.4% vs  49.2%           n= 795  49.3% vs  48.9%
usage up / teammate out   n=3014  49.5% vs  49.5%           n=3224  48.9% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 915  Vault's side won 461-454  skill -0.064 z -4.1
  agrees with the news     n= 516  Vault's side won 281-235  skill +0.000 z +0.0
  no news                  n= 803  Vault's side won 406-397  skill -0.042 z -2.5
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
  all Kalshi-priced lines: n=1439  log-loss Kalshi 0.6831  books 0.686
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 27  side won  20, price said   13.5  -> tracking (27 of 50)
PM sharp vs crowd disagree         n=  8  side won   5, price said    3.3  -> tracking (8 of 50)
PM sharp with crowd                n= 14  side won  11, price said    7.7  -> tracking (14 of 50)
Withheld props (teammate out)      lines=668  model lean won 342  overs hit 323  | would-be plays 6-10 -4.4u
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
Wk 10    358      42-25 +19.3u    42-25 +15.2u         0-2 -2.0u       0-2 -2.0u
all     4757    499-455 +45.2u  498-456 +22.6u       64-60 +7.6u     65-59 +6.8u
log-loss at the open, same 4757 props: market 0.6858  live model 0.6977  anchored 0.6854
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          18-11         +6.9u           +5.4u       16/28
1-3 days before         18-15         +4.5u           +4.6u        8/32
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
Wk 10  props n= 403  LL 0.7004 vs 0.6879  skill -0.018 z -1.3     games n=  27  LL 0.6187 vs 0.6573  skill +0.059 z +1.5
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
