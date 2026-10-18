# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3241  LL 0.7011 vs 0.6865  skill -0.021 z -3.7    n=2969  LL 0.7010 vs 0.6864  skill -0.021 z -3.6    market better than Vault
pass_att      n= 107  LL 0.7134 vs 0.6898  skill -0.034 z -1.2    n= 108  LL 0.7135 vs 0.6929  skill -0.030 z -1.0    level with the market (within noise)
pass_cmp      n= 125  LL 0.7127 vs 0.6889  skill -0.035 z -1.5    n= 126  LL 0.7139 vs 0.6823  skill -0.046 z -1.9    level with the market (within noise)
pass_td       n= 162  LL 0.6377 vs 0.6647  skill +0.041 z +1.9    n= 163  LL 0.6514 vs 0.6760  skill +0.036 z +1.7    level with the market (within noise)
pass_yd       n= 131  LL 0.7346 vs 0.6926  skill -0.060 z -2.4    n= 131  LL 0.7360 vs 0.6921  skill -0.064 z -2.6    market better than Vault
rec           n= 980  LL 0.6880 vs 0.6780  skill -0.015 z -1.4    n= 991  LL 0.6894 vs 0.6764  skill -0.019 z -1.9    level with the market (within noise)
rec_yd        n=1007  LL 0.7065 vs 0.6894  skill -0.025 z -2.4    n= 773  LL 0.7039 vs 0.6900  skill -0.020 z -1.9    market better than Vault
rush_att      n= 378  LL 0.7168 vs 0.7000  skill -0.024 z -1.4    n= 369  LL 0.7034 vs 0.6973  skill -0.009 z -0.5    level with the market (within noise)
rush_yd       n= 351  LL 0.7140 vs 0.6929  skill -0.030 z -1.4    n= 308  LL 0.7298 vs 0.6987  skill -0.044 z -1.9    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             361             52%        55%   +1.5
pass_int        171             49%        48%   -0.2
pass_td          28             64%        71%   +0.8
rec             122             55%        63%   +1.7
rec_yd           28             39%        46%   +0.8
rush_yd          12             45%        58%   +0.9
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.2pp        53%   -108.1u         51%   -170.6u
pass_att              62%   +0.1pp        57%     +9.7u         57%    +10.2u
pass_cmp              61%   +0.2pp        44%    -23.9u         44%    -19.9u
pass_td               50%   +0.0pp        61%     +9.2u         61%     +9.5u
pass_yd               60%   +0.2pp        43%    -25.2u         44%    -24.1u
rec                   59%   +0.2pp        58%    +30.5u         54%     +5.3u
rec_yd                57%   -0.1pp        52%    -14.1u         51%    -33.0u
rush_att              61%   +0.6pp        52%     -7.8u         49%    -23.7u
rush_yd               55%   +0.1pp        47%    -30.5u         47%    -43.1u
```

## Game markets (at the close)

```
games   n= 234  LL 0.7065 vs 0.6890  skill -0.025 z -1.6    level with the market (within noise)     beat close   29%  units  -16.1u
ml      n=  70  LL 0.6737 vs 0.6791  skill +0.008 z +0.2    level with the market (within noise)     beat close   41%  units   +4.7u
spread  n=  80  LL 0.7122 vs 0.6938  skill -0.026 z -1.1    level with the market (within noise)     beat close   26%  units  -13.2u
total   n=  84  LL 0.7283 vs 0.6927  skill -0.051 z -1.9    level with the market (within noise)     beat close   20%  units   -7.6u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 130  48.5% vs  49.5%           n= 144  47.9% vs  49.4%
no news                   n=1255  49.2% vs  49.5%           n=1378  49.0% vs  49.6%
usage down                n= 398  51.0% vs  49.2%           n= 457  50.5% vs  48.9%
usage up / teammate out   n=1715  50.0% vs  49.5%           n=1827  49.1% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 516  Vault's side won 268-248  skill -0.058 z -2.7
  agrees with the news     n= 310  Vault's side won 165-145  skill -0.003 z -0.1
  no news                  n= 490  Vault's side won 250-240  skill -0.046 z -2.0
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 54  toward  32 / away  13  avg move toward +0.48 pts ±0.12
spread  FanDuel     n= 44  toward  23 / away  12  avg move toward +0.16 pts ±0.16
        -> NO-GO: not ahead of the control (+0.32 pts, z +1.6)
total   Pinnacle    n= 26  toward  19 / away   6  avg move toward +0.42 pts ±0.21
total   FanDuel     n= 33  toward  19 / away   9  avg move toward +0.13 pts ±0.16
        -> too few games (26 of 50)
props   Pinnacle    n=128  toward  65 / away  10  net share toward +0.43 ±0.08
props   FanDuel     n= 35  toward  16 / away   7  net share toward +0.26 ±0.16
props   DraftKings  n= 23  toward  10 / away   3  net share toward +0.30 ±0.20
        -> NO-GO: not ahead of the controls (+0.13, z +0.6)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 14  side won   8, price said    6.5  -> tracking (14 of 50)
  all Kalshi-priced lines: n=482  log-loss Kalshi 0.6891  books 0.6903
Vault vs Kalshi (10+ pts, Kalshi)  n=164  side won  74, price said   87.0  -> no edge yet (z -2.1)
PM sharp $25k+ (all)               n= 22  side won  18, price said   11.1  -> tracking (22 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 12  side won  10, price said    6.8  -> tracking (12 of 50)
Withheld props (teammate out)      lines=200  model lean won 100  overs hit 107  | would-be plays 5-9 -4.3u
```

## Anchored shadow: live grades vs market-anchored grades (Week 4 retro)

_The anchored grade starts from the no-vig opening price and moves toward Vault only as far as Vault's measured skill in that market (weights fit on earlier weeks only, so every row is out of sample). Shadow only: the board still shows live grades. Switch only if the anchored A/B beat the live A/B on fresh weeks and its log-loss stays below the market's._

```
week    rows    live A/B: open           close   anchored A/B: open           close
Wk 2     516      84-64 +15.2u    83-65 +13.0u                 –               –
Wk 3     490       66-59 +8.4u     61-64 -0.7u       22-18 +6.5u     23-17 +7.1u
Wk 4     635       72-65 +9.0u     71-66 +3.8u       10-10 +0.7u     10-10 +0.8u
Wk 5     566       57-57 -1.6u     56-58 -7.0u        14-8 +5.2u      14-8 +4.2u
Wk 6     290       24-31 -6.8u     26-29 -3.9u         4-2 +1.7u       4-2 +1.9u
all     2497    303-276 +24.2u   297-282 +5.2u      50-38 +14.2u    51-37 +13.9u
log-loss at the open, same 2497 props: market 0.6852  live model 0.6970  anchored 0.6846
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           12-9         +2.8u           +2.0u       11/20
1-3 days before         12-10         +3.8u           +4.6u        2/21
6-24 hours before        8-10         -1.9u           -2.1u        4/16
under 6 hours           22-13         +7.2u           +3.6u        7/28
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7137 vs 0.6891  skill -0.036 z -2.3     games n=  40  LL 0.7250 vs 0.6807  skill -0.065 z -1.6
Wk  2  props n= 553  LL 0.6919 vs 0.6826  skill -0.014 z -0.8     games n=  44  LL 0.7192 vs 0.6851  skill -0.050 z -1.2
Wk  3  props n= 590  LL 0.6974 vs 0.6883  skill -0.013 z -0.9     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 676  LL 0.7079 vs 0.6950  skill -0.019 z -1.8     games n=  44  LL 0.7005 vs 0.6903  skill -0.015 z -0.4
Wk  5  props n= 597  LL 0.6944 vs 0.6794  skill -0.022 z -1.9     games n=  42  LL 0.6743 vs 0.6863  skill +0.017 z +0.6
Wk  6  props n= 311  LL 0.7016 vs 0.6805  skill -0.031 z -1.9     games n=  21  LL 0.8050 vs 0.7249  skill -0.111 z -3.4
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
