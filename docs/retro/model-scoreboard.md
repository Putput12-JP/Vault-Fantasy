# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=4752  LL 0.7010 vs 0.6859  skill -0.022 z -4.7    n=4354  LL 0.7000 vs 0.6856  skill -0.021 z -4.4    market better than Vault
pass_att      n= 171  LL 0.7081 vs 0.6894  skill -0.027 z -1.2    n= 174  LL 0.7102 vs 0.6948  skill -0.022 z -0.9    level with the market (within noise)
pass_cmp      n= 189  LL 0.7108 vs 0.6879  skill -0.033 z -1.7    n= 190  LL 0.7152 vs 0.6858  skill -0.043 z -2.1    level with the market (within noise)
pass_td       n= 226  LL 0.6590 vs 0.6687  skill +0.015 z +0.7    n= 228  LL 0.6700 vs 0.6796  skill +0.014 z +0.8    level with the market (within noise)
pass_yd       n= 196  LL 0.7285 vs 0.6910  skill -0.054 z -2.5    n= 195  LL 0.7283 vs 0.6923  skill -0.052 z -2.4    market better than Vault
rec           n=1410  LL 0.6874 vs 0.6756  skill -0.018 z -2.1    n=1433  LL 0.6899 vs 0.6762  skill -0.020 z -2.5    market better than Vault
rec_yd        n=1449  LL 0.7044 vs 0.6905  skill -0.020 z -2.5    n=1125  LL 0.7014 vs 0.6900  skill -0.017 z -2.0    market better than Vault
rush_att      n= 572  LL 0.7055 vs 0.6950  skill -0.015 z -1.1    n= 555  LL 0.6947 vs 0.6897  skill -0.007 z -0.5    level with the market (within noise)
rush_yd       n= 539  LL 0.7245 vs 0.6944  skill -0.043 z -2.4    n= 454  LL 0.7276 vs 0.6960  skill -0.045 z -2.4    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             533             51%        54%   +1.1
pass_int        238             49%        51%   +0.5
pass_td          40             64%        62%   -0.2
rec             191             55%        60%   +1.4
rec_yd           42             40%        40%   +0.1
rush_yd          20             46%        40%   -0.5
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -138.8u         51%   -223.6u
pass_att              62%   +0.1pp        56%    +10.8u         55%     +9.0u
pass_cmp              60%   +0.2pp        45%    -28.8u         46%    -23.2u
pass_td               49%   -0.1pp        58%     -0.9u         58%     -0.9u
pass_yd               57%   +0.1pp        49%    -18.4u         48%    -19.4u
rec                   59%   +0.2pp        57%    +34.9u         55%    +17.6u
rec_yd                56%   -0.1pp        51%    -47.5u         50%    -78.2u
rush_att              62%   +0.5pp        53%     -1.8u         50%    -25.6u
rush_yd               59%   +0.1pp        46%    -64.1u         45%    -76.7u
```

## Game markets (at the close)

```
games   n= 332  LL 0.6994 vs 0.6818  skill -0.026 z -2.0    level with the market (within noise)     beat close   27%  units  -17.9u
ml      n=  98  LL 0.6571 vs 0.6534  skill -0.006 z -0.2    level with the market (within noise)     beat close   43%  units   +6.2u
spread  n= 115  LL 0.7149 vs 0.6948  skill -0.029 z -1.6    level with the market (within noise)     beat close   23%  units  -21.4u
total   n= 119  LL 0.7194 vs 0.6926  skill -0.039 z -1.6    level with the market (within noise)     beat close   18%  units   -2.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 231  46.3% vs  49.3%           n= 263  44.5% vs  49.3%
no news                   n=1695  48.3% vs  49.3%           n=1865  48.3% vs  49.4%
usage down                n= 564  49.6% vs  49.1%           n= 645  49.5% vs  48.7%
usage up / teammate out   n=2608  49.7% vs  49.5%           n=2775  48.9% vs  49.4%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 781  Vault's side won 397-384  skill -0.063 z -3.6
  agrees with the news     n= 427  Vault's side won 228-199  skill -0.005 z -0.2
  no news                  n= 646  Vault's side won 332-314  skill -0.041 z -2.2
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 77  toward  48 / away  16  avg move toward +0.47 pts ±0.10
spread  FanDuel     n= 68  toward  40 / away  17  avg move toward +0.28 pts ±0.14
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.1)
total   Pinnacle    n= 40  toward  24 / away  13  avg move toward +0.21 pts ±0.17
total   FanDuel     n= 43  toward  24 / away  14  avg move toward +0.14 pts ±0.16
        -> too few games (40 of 50)
props   Pinnacle    n=249  toward 130 / away  21  net share toward +0.44 ±0.06
props   FanDuel     n= 82  toward  44 / away  11  net share toward +0.40 ±0.10
props   DraftKings  n= 39  toward  13 / away   7  net share toward +0.15 ±0.16
        -> NO-GO: not ahead of the controls (+0.04, z +0.3)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 40  side won  27, price said   20.0  -> tracking (40 of 50)
  all Kalshi-priced lines: n=1102  log-loss Kalshi 0.6821  books 0.6851
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=440  model lean won 222  overs hit 211  | would-be plays 6-10 -4.4u
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
Wk 9      37         3-3 -0.0u       3-3 +0.1u         1-0 +1.1u       1-0 +1.1u
all     3882    404-388 +17.6u   401-391 -2.4u       60-56 +8.1u     61-55 +7.8u
log-loss at the open, same 3882 props: market 0.6848  live model 0.6973  anchored 0.6844
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
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7240 vs 0.6807  skill -0.064 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7182 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7008 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7664 vs 0.7216  skill -0.062 z -2.3
Wk  7  props n= 587  LL 0.6877 vs 0.6835  skill -0.006 z -0.5     games n=  41  LL 0.7063 vs 0.6723  skill -0.051 z -1.2
Wk  8  props n= 608  LL 0.7138 vs 0.6850  skill -0.042 z -3.4     games n=  38  LL 0.6592 vs 0.6433  skill -0.025 z -0.9
Wk  9  props n=  42  LL 0.7009 vs 0.6816  skill -0.028 z -0.6     games n=   3  LL 0.5019 vs 0.5457  skill +0.080 z +0.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
