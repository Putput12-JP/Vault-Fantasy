# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=1855  LL 0.6958 vs 0.6869  skill -0.013 z -1.9    n=1664  LL 0.6942 vs 0.6862  skill -0.012 z -1.7    level with the market (within noise)
pass_att      n=  48  LL 0.7133 vs 0.6891  skill -0.035 z -0.8    n=  48  LL 0.7142 vs 0.6910  skill -0.034 z -0.7    level with the market (within noise)
pass_cmp      n=  65  LL 0.7061 vs 0.6866  skill -0.029 z -1.0    n=  65  LL 0.7084 vs 0.6733  skill -0.052 z -1.8    level with the market (within noise)
pass_td       n= 101  LL 0.6421 vs 0.6610  skill +0.029 z +1.0    n=  99  LL 0.6573 vs 0.6702  skill +0.019 z +0.7    level with the market (within noise)
pass_yd       n=  65  LL 0.7045 vs 0.6934  skill -0.016 z -0.6    n=  65  LL 0.7121 vs 0.6926  skill -0.028 z -1.0    level with the market (within noise)
rec           n= 588  LL 0.6793 vs 0.6729  skill -0.009 z -0.8    n= 582  LL 0.6816 vs 0.6750  skill -0.010 z -0.8    level with the market (within noise)
rec_yd        n= 609  LL 0.6975 vs 0.6932  skill -0.006 z -0.6    n= 449  LL 0.6912 vs 0.6925  skill +0.002 z +0.2    level with the market (within noise)
rush_att      n= 209  LL 0.7297 vs 0.7098  skill -0.028 z -1.3    n= 203  LL 0.7135 vs 0.7024  skill -0.016 z -0.7    level with the market (within noise)
rush_yd       n= 170  LL 0.7240 vs 0.6969  skill -0.039 z -1.2    n= 153  LL 0.7299 vs 0.6999  skill -0.043 z -1.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             212             51%        58%   +2.2
pass_int        105             48%        53%   +1.0
pass_td          19             64%        68%   +0.5
rec              64             55%        66%   +1.6
rec_yd           15             36%        47%   +0.8
rush_yd           9             44%        67%   +1.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -43.6u         51%    -88.7u
pass_att              70%   +0.4pp        62%     +8.6u         62%     +8.9u
pass_cmp              54%   -0.4pp        46%    -10.1u         48%     -6.5u
pass_td               50%   +0.1pp        60%     +2.9u         60%     +2.4u
pass_yd               59%   -0.0pp        41%    -15.0u         42%    -13.2u
rec                   59%   +0.1pp        57%    +17.1u         53%     -8.1u
rec_yd                57%   -0.0pp        52%     -8.7u         51%    -16.2u
rush_att              64%   +0.8pp        52%     -2.1u         49%    -13.5u
rush_yd               58%   +0.1pp        49%     -8.6u         46%    -21.9u
```

## Game markets (at the close)

```
games   n= 140  LL 0.7032 vs 0.6813  skill -0.032 z -1.4    level with the market (within noise)     beat close   36%  units   -5.8u
ml      n=  40  LL 0.6526 vs 0.6509  skill -0.003 z -0.1    level with the market (within noise)     beat close   50%  units   +4.5u
spread  n=  49  LL 0.7196 vs 0.6939  skill -0.037 z -1.1    level with the market (within noise)     beat close   37%  units   -8.9u
total   n=  51  LL 0.7273 vs 0.6929  skill -0.050 z -1.3    level with the market (within noise)     beat close   24%  units   -1.4u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  61  32.8% vs  49.9%           n=  69  37.7% vs  50.6%
no news                   n= 782  46.6% vs  49.3%           n= 876  47.1% vs  49.6%
usage down                n= 219  53.0% vs  49.1%           n= 252  50.8% vs  48.8%
usage up / teammate out   n= 907  51.7% vs  49.3%           n= 983  51.4% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 243  Vault's side won 122-121  skill -0.061 z -2.1
  agrees with the news     n= 185  Vault's side won 102-83  skill +0.040 z +1.3
  no news                  n= 265  Vault's side won 145-120  skill -0.028 z -1.0
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
props   Pinnacle    n= 29  toward  13 / away   5  net share toward +0.28 ±0.18
props   FanDuel     n=  7  toward   3 / away   1  net share toward +0.29 ±0.36
props   DraftKings  n=  5  toward   3 / away   0  net share toward +0.60 ±0.36
        -> too few props (29 of 100)
```

## Signals: Kalshi, Polymarket sharp accounts, withheld props

_Logged live before kickoff, graded here. Context only until a row says GO (50+ bets and the side winning 2+ standard errors more often than its price said)._

```
Kalshi vs books (5+ pts apart)     n=  6  side won   3, price said    2.7  -> tracking (6 of 50)
  all Kalshi-priced lines: n=70  log-loss Kalshi 0.7039  books 0.7157
Vault vs Kalshi (10+ pts, Kalshi)  n= 51  side won  18, price said   26.4  -> no edge yet (z -2.4)
PM sharp $25k+ (all)               n= 14  side won  12, price said    7.3  -> tracking (14 of 50)
PM sharp vs crowd disagree         n=  3  side won   3, price said    1.0  -> tracking (3 of 50)
PM sharp with crowd                n= 10  side won   8, price said    5.6  -> tracking (10 of 50)
Withheld props (teammate out)      lines=66  model lean won 33  overs hit 34  | would-be plays 0-1 -1.0u
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            4-1         +2.8u           +2.3u         3/4
1-3 days before           6-5         +1.0u           +0.7u        1/10
6-24 hours before         6-5         +1.3u           +1.4u         2/9
under 6 hours            11-7         +2.8u           +0.7u        3/12
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 198  LL 0.7275 vs 0.6892  skill -0.056 z -2.5     games n=  13  LL 0.7177 vs 0.6590  skill -0.089 z -1.2
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
