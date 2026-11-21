# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=6005  LL 0.7007 vs 0.6866  skill -0.020 z -5.1    n=5480  LL 0.6997 vs 0.6872  skill -0.018 z -4.4    market better than Vault
pass_att      n= 228  LL 0.7103 vs 0.6890  skill -0.031 z -1.7    n= 230  LL 0.7122 vs 0.6938  skill -0.026 z -1.4    level with the market (within noise)
pass_cmp      n= 243  LL 0.7069 vs 0.6892  skill -0.026 z -1.6    n= 242  LL 0.7094 vs 0.6860  skill -0.034 z -1.9    level with the market (within noise)
pass_td       n= 283  LL 0.6630 vs 0.6706  skill +0.011 z +0.7    n= 285  LL 0.6763 vs 0.6838  skill +0.011 z +0.7    level with the market (within noise)
pass_yd       n= 253  LL 0.7267 vs 0.6910  skill -0.052 z -2.8    n= 252  LL 0.7251 vs 0.6926  skill -0.047 z -2.6    market better than Vault
rec           n=1759  LL 0.6879 vs 0.6757  skill -0.018 z -2.5    n=1792  LL 0.6904 vs 0.6794  skill -0.016 z -2.3    market better than Vault
rec_yd        n=1813  LL 0.7015 vs 0.6917  skill -0.014 z -2.1    n=1398  LL 0.6999 vs 0.6910  skill -0.013 z -1.8    market better than Vault
rush_att      n= 730  LL 0.7107 vs 0.6958  skill -0.021 z -1.9    n= 705  LL 0.6999 vs 0.6900  skill -0.014 z -1.2    level with the market (within noise)
rush_yd       n= 696  LL 0.7207 vs 0.6945  skill -0.038 z -2.4    n= 576  LL 0.7195 vs 0.6962  skill -0.034 z -2.0    market better than Vault
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             662             52%        56%   +2.4
pass_int        295             49%        53%   +1.2
pass_td          48             64%        56%   -1.1
rec             238             55%        63%   +2.5
rec_yd           53             40%        49%   +1.3
rush_yd          26             45%        46%   +0.1
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.1pp        52%   -204.1u         51%   -287.6u
pass_att              66%   +0.3pp        54%     +5.3u         53%     +3.4u
pass_cmp              61%   +0.2pp        48%    -26.1u         48%    -22.7u
pass_td               47%   -0.1pp        56%    -16.4u         55%    -17.2u
pass_yd               56%   +0.1pp        46%    -33.6u         46%    -35.1u
rec                   59%   +0.1pp        56%     +7.8u         54%     -7.0u
rec_yd                56%   -0.1pp        51%    -49.6u         51%    -72.3u
rush_att              62%   +0.5pp        52%    -15.8u         49%    -39.8u
rush_yd               60%   +0.2pp        48%    -53.4u         47%    -73.1u
```

## Game markets (at the close)

```
games   n= 415  LL 0.6903 vs 0.6725  skill -0.026 z -2.2    market better than Vault                 beat close   28%  units  -22.5u
ml      n= 123  LL 0.6315 vs 0.6231  skill -0.013 z -0.6    level with the market (within noise)     beat close   45%  units   +0.4u
spread  n= 144  LL 0.7133 vs 0.6940  skill -0.028 z -1.5    level with the market (within noise)     beat close   24%  units  -16.1u
total   n= 148  LL 0.7170 vs 0.6927  skill -0.035 z -1.6    level with the market (within noise)     beat close   19%  units   -6.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 276  46.4% vs  49.2%           n= 320  45.3% vs  49.2%
no news                   n=2269  49.1% vs  49.4%           n=2488  49.3% vs  49.4%
usage down                n= 735  49.2% vs  49.3%           n= 837  49.3% vs  49.0%
usage up / teammate out   n=3135  48.9% vs  49.6%           n=3364  48.5% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 931  Vault's side won 467-464  skill -0.064 z -4.1
  agrees with the news     n= 535  Vault's side won 292-243  skill +0.003 z +0.2
  no news                  n= 851  Vault's side won 438-413  skill -0.039 z -2.4
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 89  toward  55 / away  21  avg move toward +0.36 pts ±0.10
spread  FanDuel     n= 83  toward  49 / away  23  avg move toward +0.24 pts ±0.14
        -> NO-GO: not ahead of the control (+0.12 pts, z +0.7)
total   Pinnacle    n= 46  toward  27 / away  16  avg move toward +0.21 pts ±0.15
total   FanDuel     n= 54  toward  33 / away  15  avg move toward +0.26 pts ±0.14
        -> too few games (46 of 50)
props   Pinnacle    n=299  toward 154 / away  21  net share toward +0.45 ±0.05
props   FanDuel     n= 89  toward  45 / away  11  net share toward +0.38 ±0.10
props   DraftKings  n= 43  toward  15 / away   7  net share toward +0.19 ±0.15
        -> NO-GO: not ahead of the controls (+0.06, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 46  side won  29, price said   22.7  -> tracking (46 of 50)
  all Kalshi-priced lines: n=1539  log-loss Kalshi 0.6844  books 0.687
Vault vs Kalshi (10+ pts, Kalshi)  n=168  side won  78, price said   89.6  -> no edge yet (z -1.8)
PM sharp $25k+ (all)               n= 27  side won  20, price said   13.5  -> tracking (27 of 50)
PM sharp vs crowd disagree         n=  8  side won   5, price said    3.3  -> tracking (8 of 50)
PM sharp with crowd                n= 14  side won  11, price said    7.7  -> tracking (14 of 50)
Withheld props (teammate out)      lines=718  model lean won 374  overs hit 344  | would-be plays 6-10 -4.4u
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
Wk 11     45         4-1 +3.4u       4-1 +3.1u         1-0 +1.3u       1-0 +1.2u
all     5008    524-476 +49.0u  522-478 +22.4u       65-60 +8.9u     66-59 +8.0u
log-loss at the open, same 5008 props: market 0.6867  live model 0.6976  anchored 0.6862
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before          18-11         +6.9u           +5.4u       16/28
1-3 days before         19-15         +5.5u           +5.8u        8/33
6-24 hours before       12-15         -3.3u           -3.9u       11/25
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
Wk 11  props n=  49  LL 0.6400 vs 0.6767  skill +0.054 z +1.7     games n=   3  LL 0.7597 vs 0.5200  skill -0.461 z -3.8
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
