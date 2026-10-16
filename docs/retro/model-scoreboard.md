# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2976  LL 0.7000 vs 0.6870  skill -0.019 z -3.1    n=2720  LL 0.6996 vs 0.6863  skill -0.019 z -3.1    market better than Vault
pass_att      n=  95  LL 0.7111 vs 0.6879  skill -0.034 z -1.1    n=  96  LL 0.7114 vs 0.6907  skill -0.030 z -0.9    level with the market (within noise)
pass_cmp      n= 113  LL 0.7156 vs 0.6895  skill -0.038 z -1.6    n= 113  LL 0.7173 vs 0.6813  skill -0.053 z -2.1    level with the market (within noise)
pass_td       n= 151  LL 0.6393 vs 0.6676  skill +0.042 z +1.9    n= 151  LL 0.6523 vs 0.6789  skill +0.039 z +1.8    level with the market (within noise)
pass_yd       n= 118  LL 0.7297 vs 0.6933  skill -0.053 z -2.1    n= 118  LL 0.7334 vs 0.6921  skill -0.059 z -2.4    market better than Vault
rec           n= 909  LL 0.6883 vs 0.6790  skill -0.014 z -1.2    n= 907  LL 0.6890 vs 0.6771  skill -0.018 z -1.6    level with the market (within noise)
rec_yd        n= 929  LL 0.7041 vs 0.6893  skill -0.021 z -2.0    n= 713  LL 0.7015 vs 0.6901  skill -0.017 z -1.4    level with the market (within noise)
rush_att      n= 345  LL 0.7172 vs 0.7017  skill -0.022 z -1.3    n= 339  LL 0.7039 vs 0.6955  skill -0.012 z -0.7    level with the market (within noise)
rush_yd       n= 316  LL 0.7114 vs 0.6925  skill -0.027 z -1.1    n= 283  LL 0.7237 vs 0.6975  skill -0.038 z -1.5    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             335             51%        54%   +1.1
pass_int        158             49%        49%   -0.1
pass_td          26             64%        69%   +0.6
rec             112             56%        61%   +1.1
rec_yd           27             39%        44%   +0.6
rush_yd          12             45%        58%   +0.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -93.5u         51%   -142.6u
pass_att              64%   +0.1pp        58%    +10.0u         58%    +10.5u
pass_cmp              61%   +0.2pp        43%    -22.0u         44%    -18.4u
pass_td               52%   +0.1pp        61%     +8.0u         61%     +7.8u
pass_yd               57%   +0.2pp        42%    -25.0u         43%    -23.8u
rec                   58%   +0.1pp        58%    +32.0u         54%     +7.2u
rec_yd                57%   -0.1pp        52%     -8.2u         52%    -16.0u
rush_att              61%   +0.6pp        51%    -11.4u         48%    -23.5u
rush_yd               54%   +0.1pp        47%    -28.4u         46%    -42.5u
```

## Game markets (at the close)

```
games   n= 216  LL 0.6987 vs 0.6864  skill -0.018 z -1.0    level with the market (within noise)     beat close   29%  units   -1.3u
ml      n=  64  LL 0.6602 vs 0.6716  skill +0.017 z +0.5    level with the market (within noise)     beat close   42%  units   +9.4u
spread  n=  74  LL 0.7064 vs 0.6930  skill -0.019 z -0.7    level with the market (within noise)     beat close   27%  units   -7.2u
total   n=  78  LL 0.7230 vs 0.6924  skill -0.044 z -1.6    level with the market (within noise)     beat close   21%  units   -3.5u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 129  48.8% vs  49.5%           n= 142  48.6% vs  49.4%
no news                   n=1086  48.2% vs  49.5%           n=1202  48.4% vs  49.6%
usage down                n= 363  51.0% vs  49.2%           n= 417  50.6% vs  48.9%
usage up / teammate out   n=1628  49.8% vs  49.5%           n=1731  48.9% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 484  Vault's side won 250-234  skill -0.062 z -2.7
  agrees with the news     n= 284  Vault's side won 152-132  skill -0.001 z -0.0
  no news                  n= 440  Vault's side won 232-208  skill -0.037 z -1.5
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 47  toward  27 / away  11  avg move toward +0.45 pts ±0.11
spread  FanDuel     n= 40  toward  21 / away  11  avg move toward +0.16 pts ±0.15
        -> too few games (47 of 50)
total   Pinnacle    n= 23  toward  17 / away   5  avg move toward +0.48 pts ±0.16
total   FanDuel     n= 28  toward  17 / away   8  avg move toward +0.10 pts ±0.17
        -> too few games (23 of 50)
props   Pinnacle    n=102  toward  51 / away  10  net share toward +0.40 ±0.09
props   FanDuel     n= 30  toward  13 / away   4  net share toward +0.30 ±0.17
props   DraftKings  n= 23  toward   9 / away   3  net share toward +0.26 ±0.20
        -> NO-GO: not ahead of the controls (+0.10, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=376  log-loss Kalshi 0.6847  books 0.686
Vault vs Kalshi (10+ pts, Kalshi)  n=162  side won  72, price said   85.9  -> no edge yet (z -2.2)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=161  model lean won 86  overs hit 84  | would-be plays 5-8 -3.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6      41         7-0 +7.0u       7-0 +6.4u         1-0 +0.7u       1-0 +0.7u
all     2248    286-245 +38.0u  278-253 +15.4u      47-36 +13.2u    48-35 +12.7u
log-loss at the open, same 2248 props: market 0.6850  live model 0.6948  anchored 0.6841
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           11-8         +3.0u           +2.0u       10/18
1-3 days before          12-9         +4.8u           +5.6u        2/20
6-24 hours before        8-10         -1.9u           -2.1u        4/16
under 6 hours           21-13         +6.3u           +2.6u        6/27
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7254 vs 0.6807  skill -0.066 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7197 vs 0.6851  skill -0.051 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6656 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7004 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n=  46  LL 0.6300 vs 0.6790  skill +0.072 z +2.4     games n=   3  LL 0.8266 vs 0.7537  skill -0.097 z -1.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
