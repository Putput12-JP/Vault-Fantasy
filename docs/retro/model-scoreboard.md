# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4793  LL 0.7013 vs 0.6859  skill -0.022 z -4.8    n=4393  LL 0.7004 vs 0.6857  skill -0.021 z -4.5    market better than Vault
pass_att      n= 173  LL 0.7074 vs 0.6897  skill -0.026 z -1.1    n= 176  LL 0.7095 vs 0.6943  skill -0.022 z -0.9    level with the market (within noise)
pass_cmp      n= 191  LL 0.7107 vs 0.6880  skill -0.033 z -1.7    n= 191  LL 0.7157 vs 0.6859  skill -0.043 z -2.1    level with the market (within noise)
pass_td       n= 228  LL 0.6595 vs 0.6697  skill +0.015 z +0.8    n= 230  LL 0.6704 vs 0.6809  skill +0.015 z +0.8    level with the market (within noise)
pass_yd       n= 198  LL 0.7293 vs 0.6911  skill -0.055 z -2.6    n= 197  LL 0.7294 vs 0.6922  skill -0.054 z -2.5    market better than Vault
rec           n=1421  LL 0.6879 vs 0.6754  skill -0.019 z -2.2    n=1444  LL 0.6904 vs 0.6763  skill -0.021 z -2.6    market better than Vault
rec_yd        n=1460  LL 0.7045 vs 0.6905  skill -0.020 z -2.5    n=1135  LL 0.7019 vs 0.6901  skill -0.017 z -2.1    market better than Vault
rush_att      n= 578  LL 0.7056 vs 0.6949  skill -0.015 z -1.2    n= 561  LL 0.6941 vs 0.6891  skill -0.007 z -0.5    level with the market (within noise)
rush_yd       n= 544  LL 0.7253 vs 0.6944  skill -0.044 z -2.5    n= 459  LL 0.7286 vs 0.6960  skill -0.047 z -2.4    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             538             51%        54%   +1.3
pass_int        240             49%        51%   +0.5
pass_td          40             64%        62%   -0.2
rec             193             55%        60%   +1.6
rec_yd           43             40%        42%   +0.2
rush_yd          20             46%        40%   -0.5
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -144.5u         51%   -230.1u
pass_att              63%   +0.2pp        55%     +8.8u         55%     +7.0u
pass_cmp              60%   +0.2pp        45%    -28.9u         46%    -23.2u
pass_td               49%   -0.1pp        58%     -1.1u         58%     -1.1u
pass_yd               57%   +0.1pp        48%    -20.4u         48%    -21.4u
rec                   59%   +0.2pp        57%    +31.6u         54%    +13.4u
rec_yd                56%   -0.1pp        51%    -50.0u         50%    -79.8u
rush_att              61%   +0.5pp        53%     -2.4u         50%    -26.2u
rush_yd               59%   +0.1pp        46%    -61.5u         46%    -75.1u
```

## Game markets (at the close)

```
games   n= 335  LL 0.6981 vs 0.6813  skill -0.025 z -1.9    level with the market (within noise)     beat close   28%  units  -15.4u
ml      n=  99  LL 0.6547 vs 0.6516  skill -0.005 z -0.2    level with the market (within noise)     beat close   43%  units   +6.8u
spread  n= 116  LL 0.7144 vs 0.6952  skill -0.028 z -1.5    level with the market (within noise)     beat close   24%  units  -20.6u
total   n= 120  LL 0.7182 vs 0.6924  skill -0.037 z -1.6    level with the market (within noise)     beat close   18%  units   -1.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 231  46.3% vs  49.3%           n= 263  44.5% vs  49.3%
no news                   n=1733  48.1% vs  49.3%           n=1905  48.0% vs  49.4%
usage down                n= 564  49.6% vs  49.1%           n= 645  49.5% vs  48.7%
usage up / teammate out   n=2618  49.8% vs  49.5%           n=2786  48.9% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 783  Vault's side won 397-386  skill -0.065 z -3.7
  agrees with the news     n= 429  Vault's side won 228-201  skill -0.008 z -0.4
  no news                  n= 657  Vault's side won 338-319  skill -0.042 z -2.2
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 84  toward  51 / away  20  avg move toward +0.41 pts ±0.10
spread  FanDuel     n= 69  toward  41 / away  17  avg move toward +0.28 pts ±0.13
        -> NO-GO: not ahead of the control (+0.13 pts, z +0.8)
total   Pinnacle    n= 43  toward  26 / away  14  avg move toward +0.22 pts ±0.16
total   FanDuel     n= 43  toward  24 / away  14  avg move toward +0.14 pts ±0.16
        -> too few games (43 of 50)
props   Pinnacle    n=252  toward 131 / away  20  net share toward +0.44 ±0.06
props   FanDuel     n= 82  toward  44 / away  11  net share toward +0.40 ±0.10
props   DraftKings  n= 39  toward  13 / away   7  net share toward +0.15 ±0.16
        -> NO-GO: not ahead of the controls (+0.04, z +0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 41  side won  27, price said   20.5  -> tracking (41 of 50)
  all Kalshi-priced lines: n=1119  log-loss Kalshi 0.6829  books 0.6856
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=446  model lean won 227  overs hit 216  | would-be plays 6-10 -4.4u
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
Wk 9      76         6-8 -2.0u       6-8 -2.6u         1-1 +0.1u       1-1 +0.1u
all     3921    407-393 +15.6u   404-396 -5.1u       60-57 +7.0u     61-56 +6.8u
log-loss at the open, same 3921 props: market 0.6848  live model 0.6978  anchored 0.6845
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          17-10         +6.7u           +5.3u       15/26
1-3 days before         18-14         +5.5u           +3.7u        8/31
6-24 hours before       12-13         -1.3u           -1.9u        9/23
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7245 vs 0.6807  skill -0.064 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7187 vs 0.6851  skill -0.049 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7006 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7670 vs 0.7216  skill -0.063 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7066 vs 0.6723  skill -0.051 z -1.2
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6593 vs 0.6433  skill -0.025 z -0.9
Wk  9  props n=  83  LL 0.7205 vs 0.6845  skill -0.052 z -1.6     games n=   6  LL 0.5132 vs 0.5881  skill +0.127 z +1.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
