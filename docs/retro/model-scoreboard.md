# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=3864  LL 0.6992 vs 0.6868  skill -0.018 z -3.5    n=3555  LL 0.6991 vs 0.6861  skill -0.019 z -3.5    market better than Vault
pass_att      n= 132  LL 0.7044 vs 0.6877  skill -0.024 z -0.9    n= 135  LL 0.7046 vs 0.6952  skill -0.014 z -0.5    level with the market (within noise)
pass_cmp      n= 152  LL 0.7131 vs 0.6878  skill -0.037 z -1.7    n= 154  LL 0.7143 vs 0.6841  skill -0.044 z -2.0    level with the market (within noise)
pass_td       n= 187  LL 0.6491 vs 0.6706  skill +0.032 z +1.5    n= 190  LL 0.6601 vs 0.6799  skill +0.029 z +1.4    level with the market (within noise)
pass_yd       n= 158  LL 0.7242 vs 0.6940  skill -0.043 z -1.8    n= 158  LL 0.7228 vs 0.6933  skill -0.043 z -1.8    level with the market (within noise)
rec           n=1155  LL 0.6863 vs 0.6774  skill -0.013 z -1.4    n=1174  LL 0.6879 vs 0.6759  skill -0.018 z -1.9    level with the market (within noise)
rec_yd        n=1191  LL 0.7040 vs 0.6892  skill -0.021 z -2.3    n= 923  LL 0.7023 vs 0.6896  skill -0.018 z -1.9    market better than Vault
rush_att      n= 460  LL 0.7102 vs 0.6997  skill -0.015 z -1.0    n= 449  LL 0.6978 vs 0.6944  skill -0.005 z -0.3    level with the market (within noise)
rush_yd       n= 429  LL 0.7153 vs 0.6950  skill -0.029 z -1.5    n= 372  LL 0.7297 vs 0.6974  skill -0.046 z -2.2    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             429             51%        54%   +1.2
pass_int        198             49%        50%   +0.3
pass_td          34             64%        65%   +0.1
rec             149             55%        61%   +1.5
rec_yd           34             40%        41%   +0.2
rush_yd          14             45%        50%   +0.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   58%   +0.1pp        53%    -79.2u         52%   -147.3u
pass_att              63%   +0.2pp        58%    +13.6u         57%    +11.4u
pass_cmp              60%   +0.2pp        47%    -19.4u         47%    -15.5u
pass_td               49%   -0.1pp        58%     +0.3u         58%     +1.6u
pass_yd               58%   +0.2pp        49%    -13.5u         49%    -13.1u
rec                   59%   +0.1pp        58%    +50.2u         55%    +25.2u
rec_yd                55%   -0.1pp        52%    -20.9u         51%    -39.7u
rush_att              63%   +0.7pp        53%     +0.1u         50%    -17.2u
rush_yd               57%   +0.1pp        46%    -46.9u         46%    -56.4u
```

## Game markets (at the close)

```
games   n= 276  LL 0.7100 vs 0.6923  skill -0.026 z -1.8    level with the market (within noise)     beat close   28%  units  -17.1u
ml      n=  82  LL 0.6870 vs 0.6896  skill +0.004 z +0.1    level with the market (within noise)     beat close   41%  units   +8.9u
spread  n=  95  LL 0.7158 vs 0.6945  skill -0.031 z -1.5    level with the market (within noise)     beat close   23%  units  -18.6u
total   n=  99  LL 0.7236 vs 0.6924  skill -0.045 z -1.9    level with the market (within noise)     beat close   20%  units   -7.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n= 165  48.5% vs  49.5%           n= 187  47.6% vs  49.4%
no news                   n=1484  47.6% vs  49.4%           n=1613  47.9% vs  49.5%
usage down                n= 469  51.2% vs  49.2%           n= 532  50.9% vs  48.9%
usage up / teammate out   n=2066  50.6% vs  49.5%           n=2198  49.4% vs  49.5%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 623  Vault's side won 317-306  skill -0.062 z -3.2
  agrees with the news     n= 355  Vault's side won 190-165  skill -0.005 z -0.2
  no news                  n= 581  Vault's side won 305-276  skill -0.026 z -1.3
```

## Sharp-book lead: does Pinnacle move first?

_When Pinnacle's no-vig line sat half a point or more off the recreational books 3+ hours out, did those books move toward it by kickoff? FanDuel is the control: an off-the-pack book gets pulled back toward the pack whoever it is, so Pinnacle only counts as sharp if it clearly beats FanDuel. Weeks 1-3 are replayed from the saved odds feed; later weeks are logged live._

```
spread  Pinnacle    n= 68  toward  40 / away  15  avg move toward +0.48 pts ±0.11
spread  FanDuel     n= 58  toward  32 / away  15  avg move toward +0.30 pts ±0.15
        -> NO-GO: not ahead of the control (+0.19 pts, z +1.0)
total   Pinnacle    n= 34  toward  21 / away  11  avg move toward +0.30 pts ±0.18
total   FanDuel     n= 38  toward  21 / away  12  avg move toward +0.05 pts ±0.15
        -> too few games (34 of 50)
props   Pinnacle    n=173  toward  84 / away  12  net share toward +0.42 ±0.07
props   FanDuel     n= 45  toward  23 / away   8  net share toward +0.33 ±0.14
props   DraftKings  n= 27  toward  10 / away   4  net share toward +0.22 ±0.19
        -> NO-GO: not ahead of the controls (+0.08, z +0.5)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n= 24  side won  14, price said   11.8  -> tracking (24 of 50)
  all Kalshi-priced lines: n=738  log-loss Kalshi 0.6867  books 0.6888
Vault vs Kalshi (10+ pts, Kalshi)  n=166  side won  76, price said   88.2  -> no edge yet (z -1.9)
PM sharp $25k+ (all)               n= 23  side won  18, price said   11.3  -> tracking (23 of 50)
PM sharp vs crowd disagree         n=  5  side won   4, price said    1.8  -> tracking (5 of 50)
PM sharp with crowd                n= 13  side won  10, price said    7.0  -> tracking (13 of 50)
Withheld props (teammate out)      lines=276  model lean won 136  overs hit 139  | would-be plays 6-9 -3.4u
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
Wk 7     329       22-26 -2.5u     22-26 -4.0u         2-4 -1.6u       2-4 -1.4u
all     3083    345-326 +18.8u   340-331 -1.9u      54-46 +11.7u    55-45 +11.8u
log-loss at the open, same 3083 props: market 0.6851  live model 0.6955  anchored 0.6842
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before           16-9         +6.8u           +5.4u       13/24
1-3 days before         15-13         +3.6u           +4.2u        5/27
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
Wk  6  props n= 585  LL 0.7006 vs 0.6834  skill -0.025 z -2.0     games n=  37  LL 0.7661 vs 0.7216  skill -0.062 z -2.3
Wk  7  props n= 349  LL 0.6817 vs 0.6896  skill +0.011 z +0.8     games n=  26  LL 0.7423 vs 0.7064  skill -0.051 z -1.6
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
