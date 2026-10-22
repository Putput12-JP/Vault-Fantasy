# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3520  LL 0.7013 vs 0.6864  skill -0.022 z -3.9    n=3230  LL 0.7016 vs 0.6863  skill -0.022 z -3.9    market better than Vault
pass_att      n= 117  LL 0.7162 vs 0.6887  skill -0.040 z -1.4    n= 119  LL 0.7190 vs 0.6935  skill -0.037 z -1.2    level with the market (within noise)
pass_cmp      n= 137  LL 0.7200 vs 0.6887  skill -0.045 z -2.0    n= 138  LL 0.7207 vs 0.6850  skill -0.052 z -2.2    market better than Vault
pass_td       n= 174  LL 0.6426 vs 0.6684  skill +0.039 z +1.8    n= 175  LL 0.6553 vs 0.6780  skill +0.034 z +1.6    level with the market (within noise)
pass_yd       n= 143  LL 0.7369 vs 0.6924  skill -0.064 z -2.6    n= 143  LL 0.7360 vs 0.6921  skill -0.063 z -2.5    market better than Vault
rec           n=1062  LL 0.6886 vs 0.6782  skill -0.015 z -1.6    n=1077  LL 0.6907 vs 0.6764  skill -0.021 z -2.1    level with the market (within noise)
rec_yd        n=1089  LL 0.7060 vs 0.6890  skill -0.025 z -2.5    n= 838  LL 0.7029 vs 0.6894  skill -0.019 z -1.9    market better than Vault
rush_att      n= 414  LL 0.7122 vs 0.6994  skill -0.018 z -1.1    n= 404  LL 0.6984 vs 0.6960  skill -0.004 z -0.2    level with the market (within noise)
rush_yd       n= 384  LL 0.7135 vs 0.6924  skill -0.030 z -1.4    n= 336  LL 0.7327 vs 0.6980  skill -0.050 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             391             52%        55%   +1.5
pass_int        183             49%        50%   +0.2
pass_td          30             64%        70%   +0.7
rec             135             55%        62%   +1.4
rec_yd           29             40%        48%   +1.0
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%   -117.7u         51%   -182.3u
pass_att              64%   +0.1pp        56%     +8.3u         56%     +8.6u
pass_cmp              62%   +0.2pp        45%    -22.2u         46%    -18.5u
pass_td               51%   +0.1pp        59%     +4.1u         59%     +4.7u
pass_yd               59%   +0.2pp        44%    -24.5u         45%    -23.1u
rec                   59%   +0.2pp        58%    +29.8u         54%     +7.1u
rec_yd                56%   -0.1pp        52%    -14.0u         51%    -38.2u
rush_att              61%   +0.6pp        52%     -3.3u         50%    -19.4u
rush_yd               56%   +0.1pp        47%    -36.5u         47%    -47.9u
```

## Game markets (at the close)

```
games   n= 250  LL 0.7066 vs 0.6908  skill -0.023 z -1.5    level with the market (within noise)     beat close   29%  units  -12.7u
ml      n=  74  LL 0.6770 vs 0.6852  skill +0.012 z +0.4    level with the market (within noise)     beat close   45%  units  +10.6u
spread  n=  86  LL 0.7134 vs 0.6940  skill -0.028 z -1.2    level with the market (within noise)     beat close   26%  units  -15.4u
total   n=  90  LL 0.7246 vs 0.6924  skill -0.046 z -1.8    level with the market (within noise)     beat close   19%  units   -7.9u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1281  47.9% vs  49.5%           n=1408  48.1% vs  49.6%
usage down                n= 417  50.8% vs  49.2%           n= 475  50.5% vs  48.8%
usage up / teammate out   n=1940  50.8% vs  49.5%           n=2062  49.6% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 582  Vault's side won 296-286  skill -0.065 z -3.2
  agrees with the news     n= 326  Vault's side won 174-152  skill -0.002 z -0.1
  no news                  n= 512  Vault's side won 261-251  skill -0.045 z -2.1
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 62  toward  36 / away  15  avg move toward +0.45 pts ±0.11
spread  FanDuel     n= 50  toward  25 / away  14  avg move toward +0.18 pts ±0.15
        -> NO-GO: not ahead of the control (+0.27 pts, z +1.5)
total   Pinnacle    n= 31  toward  21 / away   9  avg move toward +0.38 pts ±0.18
total   FanDuel     n= 37  toward  21 / away  11  avg move toward +0.08 pts ±0.16
        -> too few games (31 of 50)
props   Pinnacle    n=132  toward  68 / away  10  net share toward +0.44 ±0.08
props   FanDuel     n= 38  toward  16 / away   8  net share toward +0.21 ±0.16
props   DraftKings  n= 26  toward  10 / away   3  net share toward +0.27 ±0.19
        -> NO-GO: not ahead of the controls (+0.17, z +0.8)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 18  side won  10, price said    8.6  -> tracking (18 of 50)
  all Kalshi-priced lines: n=587  log-loss Kalshi 0.6868  books 0.6879
Vault vs Kalshi (10+ pts, Kalshi)  n=165  side won  75, price said   87.7  -> no edge yet (z -2.0)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=225  model lean won 109  overs hit 112  | would-be plays 5-9 -4.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     551      44-56 -10.8u     47-53 -8.0u         6-6 +0.7u       6-6 +1.2u
all     2758    323-301 +20.3u   318-306 +1.1u      52-42 +13.2u    53-41 +13.2u
log-loss at the open, same 2758 props: market 0.6852  live model 0.6981  anchored 0.6847
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
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7236 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7178 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6744 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 590  LL 0.7027 vs 0.6832  skill -0.029 z -2.2     games n=  37  LL 0.7661 vs 0.7216  skill -0.062 z -2.3
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
