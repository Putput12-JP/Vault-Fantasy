# Model scoreboard: Vault vs. the market

_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. **Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. No-vig = power method._

## Props

```
market        at the CLOSE                                        at the OPEN                                         verdict (close)
all           n=2135  LL 0.6944 vs 0.6882  skill -0.009 z -1.5    n=1927  LL 0.6947 vs 0.6888  skill -0.009 z -1.4    level with the market (within noise)
pass_att      n=  62  LL 0.7071 vs 0.6872  skill -0.029 z -0.8    n=  62  LL 0.7139 vs 0.6935  skill -0.029 z -0.8    level with the market (within noise)
pass_cmp      n=  78  LL 0.7089 vs 0.6903  skill -0.027 z -1.0    n=  78  LL 0.7084 vs 0.6754  skill -0.049 z -1.8    level with the market (within noise)
pass_td       n= 114  LL 0.6471 vs 0.6733  skill +0.039 z +1.5    n= 113  LL 0.6670 vs 0.6885  skill +0.031 z +1.2    level with the market (within noise)
pass_yd       n=  79  LL 0.7060 vs 0.6933  skill -0.018 z -0.7    n=  79  LL 0.7099 vs 0.6925  skill -0.025 z -1.0    level with the market (within noise)
rec           n= 668  LL 0.6796 vs 0.6749  skill -0.007 z -0.6    n= 663  LL 0.6821 vs 0.6790  skill -0.005 z -0.4    level with the market (within noise)
rec_yd        n= 689  LL 0.6961 vs 0.6925  skill -0.005 z -0.5    n= 513  LL 0.6934 vs 0.6916  skill -0.003 z -0.3    level with the market (within noise)
rush_att      n= 242  LL 0.7224 vs 0.7101  skill -0.017 z -0.9    n= 236  LL 0.7082 vs 0.7038  skill -0.006 z -0.3    level with the market (within noise)
rush_yd       n= 203  LL 0.7165 vs 0.6968  skill -0.028 z -1.0    n= 183  LL 0.7250 vs 0.6994  skill -0.037 z -1.3    level with the market (within noise)
```

### 0.5 lines: market vs. result (capture watch)

_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. |z| of 3+ means the banked prices are coming from another line again._

```
market            n  market P(over)  over rate      z
all             242             51%        57%   +1.9
pass_int        119             49%        52%   +0.7
pass_td          21             63%        67%   +0.3
rec              76             56%        63%   +1.3
rec_yd           17             36%        47%   +0.9
rush_yd           9             44%        67%   +1.4
```

### Props: line value and units on Vault's side

```
market         beat close  avg CLV    open: win   units    close: win   units
all                   59%   +0.2pp        53%    -51.2u         51%    -95.3u
pass_att              70%   +0.2pp        60%     +8.1u         60%     +8.1u
pass_cmp              61%   +0.1pp        46%    -11.7u         47%     -8.1u
pass_td               53%   +0.2pp        57%     -0.3u         57%     -1.1u
pass_yd               60%   -0.0pp        41%    -17.6u         42%    -15.8u
rec                   59%   +0.1pp        58%    +26.9u         54%     -1.2u
rec_yd                56%   -0.0pp        52%    -12.4u         52%    -17.4u
rush_att              63%   +0.7pp        53%     -0.3u         50%    -10.9u
rush_yd               59%   +0.1pp        50%     -8.1u         47%    -22.6u
```

## Game markets (at the close)

```
games   n= 160  LL 0.7016 vs 0.6868  skill -0.021 z -1.1    level with the market (within noise)     beat close   31%  units   -0.5u
ml      n=  46  LL 0.6615 vs 0.6709  skill +0.014 z +0.3    level with the market (within noise)     beat close   43%  units   +8.5u
spread  n=  56  LL 0.7130 vs 0.6939  skill -0.028 z -0.9    level with the market (within noise)     beat close   32%  units   -8.3u
total   n=  58  LL 0.7223 vs 0.6926  skill -0.043 z -1.2    level with the market (within noise)     beat close   21%  units   -0.7u
```

## News triggers (plan Week 3)

_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big disagreements that agree with the news beat the ones without news._

```
trigger                   OPEN: over hit vs market said     CLOSE: over hit vs market said
mixed                     n=  69  39.1% vs  49.7%           n=  77  42.9% vs  50.5%
no news                   n= 919  46.6% vs  49.5%           n=1020  46.8% vs  49.7%
usage down                n= 282  53.9% vs  48.9%           n= 324  52.2% vs  48.8%
usage up / teammate out   n=1007  51.3% vs  49.3%           n=1087  50.9% vs  49.3%

Vault vs market disagreements of 8+ pts (close):
  against the news         n= 282  Vault's side won 147-135  skill -0.042 z -1.6
  agrees with the news     n= 202  Vault's side won 110-92  skill +0.033 z +1.1
  no news                  n= 300  Vault's side won 170-130  skill -0.010 z -0.4
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
Kalshi vs books (5+ pts apart)     n= 12  side won   7, price said    5.6  -> tracking (12 of 50)
  all Kalshi-priced lines: n=164  log-loss Kalshi 0.6985  books 0.7057
Vault vs Kalshi (10+ pts, Kalshi)  n=129  side won  52, price said   66.3  -> no edge yet (z -2.5)
PM sharp $25k+ (all)               n= 18  side won  15, price said    9.1  -> tracking (18 of 50)
PM sharp vs crowd disagree         n=  4  side won   3, price said    1.3  -> tracking (4 of 50)
PM sharp with crowd                n= 10  side won   8, price said    5.6  -> tracking (10 of 50)
Withheld props (teammate out)      lines=91  model lean won 50  overs hit 48  | would-be plays 0-2 -2.0u
```

## Timing: Best Bets by how early they posted (plan Weeks 3-4)

_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted with, then re-priced at the close. If posting early is where the value is, the gap between the two should be widest in the earliest rows._

```
posted                 record  units posted  units at close  beat close
3+ days before            8-2         +5.8u           +5.0u         6/9
1-3 days before           9-8         +1.8u           +1.4u        1/16
6-24 hours before         6-5         +1.3u           +1.4u         2/9
under 6 hours            11-8         +1.8u           -0.3u        3/13
```

- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.

## By week (props at the close / games at the close)

```
Wk  1  props n= 514  LL 0.7014 vs 0.6891  skill -0.018 z -1.5     games n=  40  LL 0.7233 vs 0.6807  skill -0.063 z -1.6
Wk  2  props n= 553  LL 0.6853 vs 0.6826  skill -0.004 z -0.3     games n=  44  LL 0.7175 vs 0.6851  skill -0.047 z -1.1
Wk  3  props n= 590  LL 0.6900 vs 0.6883  skill -0.003 z -0.2     games n=  43  LL 0.6657 vs 0.6847  skill +0.028 z +0.7
Wk  4  props n= 478  LL 0.7028 vs 0.6936  skill -0.013 z -1.1     games n=  33  LL 0.7007 vs 0.6993  skill -0.002 z -0.1
```

## How to read this

- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. **z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real difference, under 2 is noise. Below 30 bets the verdict says too few.
- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), so props lean on skill, calibration and units by market and side.
- Open vs. close units show what betting when Vault grades is worth versus waiting.

---
_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._
