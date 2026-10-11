# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2718  LL 0.7011 vs 0.6869  skill -0.021 z -3.2    n=2481  LL 0.7000 vs 0.6866  skill -0.019 z -2.9    market better than Vault
pass_att      n=  85  LL 0.7109 vs 0.6874  skill -0.034 z -1.1    n=  86  LL 0.7133 vs 0.6915  skill -0.032 z -0.9    level with the market (within noise)
pass_cmp      n= 104  LL 0.7164 vs 0.6895  skill -0.039 z -1.6    n= 104  LL 0.7182 vs 0.6798  skill -0.057 z -2.2    level with the market (within noise)
pass_td       n= 141  LL 0.6308 vs 0.6621  skill +0.047 z +2.2    n= 141  LL 0.6461 vs 0.6744  skill +0.042 z +2.0    Vault better than the market
pass_yd       n= 107  LL 0.7269 vs 0.6926  skill -0.050 z -2.0    n= 107  LL 0.7307 vs 0.6923  skill -0.055 z -2.2    level with the market (within noise)
rec           n= 834  LL 0.6907 vs 0.6788  skill -0.018 z -1.5    n= 832  LL 0.6902 vs 0.6769  skill -0.020 z -1.7    level with the market (within noise)
rec_yd        n= 854  LL 0.7058 vs 0.6894  skill -0.024 z -2.0    n= 652  LL 0.7033 vs 0.6909  skill -0.018 z -1.5    market better than Vault
rush_att      n= 314  LL 0.7155 vs 0.7036  skill -0.017 z -0.9    n= 307  LL 0.7015 vs 0.6987  skill -0.004 z -0.2    level with the market (within noise)
rush_yd       n= 279  LL 0.7189 vs 0.6939  skill -0.036 z -1.4    n= 252  LL 0.7267 vs 0.6980  skill -0.041 z -1.5    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             308             51%        55%   +1.4
pass_int        147             49%        48%   -0.2
pass_td          26             64%        69%   +0.6
rec             100             55%        63%   +1.6
rec_yd           25             39%        48%   +1.0
rush_yd          10             44%        60%   +1.0
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%    -82.2u         51%   -138.0u
pass_att              67%   +0.2pp        57%     +6.9u         57%     +7.1u
pass_cmp              59%   +0.1pp        43%    -20.6u         44%    -16.9u
pass_td               53%   +0.1pp        60%     +6.5u         60%     +6.1u
pass_yd               58%   +0.1pp        43%    -21.4u         44%    -20.1u
rec                   59%   +0.1pp        58%    +24.8u         54%     -4.8u
rec_yd                56%   -0.1pp        52%    -10.6u         52%    -17.9u
rush_att              61%   +0.6pp        52%     -2.4u         50%    -13.3u
rush_yd               55%   +0.2pp        47%    -26.5u         45%    -42.0u
```

## Game markets (at the close)

```
games   n= 198  LL 0.6959 vs 0.6844  skill -0.017 z -0.9    level with the market (within noise)     beat close   30%  units   +2.2u
ml      n=  58  LL 0.6512 vs 0.6634  skill +0.018 z +0.5    level with the market (within noise)     beat close   41%  units  +10.5u
spread  n=  68  LL 0.7048 vs 0.6932  skill -0.017 z -0.6    level with the market (within noise)     beat close   29%  units   -5.0u
total   n=  72  LL 0.7236 vs 0.6929  skill -0.044 z -1.5    level with the market (within noise)     beat close   22%  units   -3.3u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 102  49.0% vs  49.5%           n= 112  49.1% vs  49.8%
no news                   n=1078  48.9% vs  49.5%           n=1184  49.2% vs  49.6%
usage down                n= 365  50.4% vs  49.1%           n= 416  50.2% vs  48.8%
usage up / teammate out   n=1382  49.6% vs  49.5%           n=1480  48.6% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 422  Vault's side won 220-202  skill -0.058 z -2.4
  agrees with the news     n= 264  Vault's side won 137-127  skill -0.010 z -0.3
  no news                  n= 436  Vault's side won 228-208  skill -0.047 z -1.9
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 29  toward  19 / away   7  avg move toward +0.50 pts ±0.14
spread  FanDuel     n= 22  toward  14 / away   6  avg move toward +0.34 pts ±0.23
        -> too few games (29 of 50)
total   Pinnacle    n= 13  toward   9 / away   3  avg move toward +0.44 pts ±0.22
total   FanDuel     n= 13  toward   9 / away   2  avg move toward +0.19 pts ±0.19
        -> too few games (13 of 50)
props   Pinnacle    n= 61  toward  26 / away   6  net share toward +0.33 ±0.12
props   FanDuel     n= 18  toward   8 / away   3  net share toward +0.28 ±0.23
props   DraftKings  n= 17  toward   8 / away   1  net share toward +0.41 ±0.22
        -> too few props (61 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 12  side won   6, price said    5.6  -> tracking (12 of 50)
  all Kalshi-priced lines: n=258  log-loss Kalshi 0.6838  books 0.6845
Vault vs Kalshi (10+ pts, Kalshi)  n=134  side won  60, price said   70.9  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=125  model lean won 66  overs hit 60  | would-be plays 4-5 -1.2u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     368       37-32 +3.9u     34-35 -4.4u        11-6 +3.7u      11-6 +2.6u
all     2009    259-220 +36.5u  249-230 +11.7u      43-34 +10.9u    44-33 +10.5u
log-loss at the open, same 2009 props: market 0.6852  live model 0.6948  anchored 0.6841
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           10-6         +4.0u           +3.1u        9/15
1-3 days before           9-9         +0.8u           +2.1u        1/17
6-24 hours before         7-8         -0.8u           -1.0u        3/13
under 6 hours           16-12         +2.5u           +0.1u        6/22
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7237 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7179 vs 0.6851  skill -0.048 z -1.1
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7009 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 385  LL 0.6912 vs 0.6737  skill -0.026 z -1.8     games n=  27  LL 0.6590 vs 0.6784  skill +0.029 z +0.8
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
