# Simulation challenger: results

Generated 2026-10-12T18:18Z by `nba/scripts/build_sim_challenger.py`. Rules: docs/sim-challenger.md. Fit on 2024-25, tested on 2025-26,
identical player-games and prices for every variant. Lower log loss is better. `dLL` is the paired log-loss difference against v2
(negative = better than v2), with a game-clustered standard error. `flip` is how often the variant lands on the other side of the price
from v2. `gap` is the root-mean-square distance of its probability from v2's, next to what pure Monte Carlo noise at that N predicts.

## espn_close

### pts (n = 884, market log loss 0.692)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.6967 | 0.2514 | +0.0 (0.0) | 1.24 | 0.0% | 0.0 |
| sim10k | 0.697 | 0.2516 | +0.0003 (0.0004) | 1.16 | 2.0% | 0.0033 (0.005) |
| sim50 | 0.6999 | 0.253 | +0.0032 (0.0042) | 1.57 | 18.3% | 0.0486 (0.0701) |
| sam50 | 0.7033 | 0.2547 | +0.0066 (0.0054) | 0.79 | 21.9% | 0.0523 (0.0701) |
| sam50_shown | 0.7273 | 0.2651 | +0.0307 (0.0098) | 1.08 | 19.6% | 0.0957 (0.0701) |

### reb (n = 901, market log loss 0.6937)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.6955 | 0.2511 | +0.0 (0.0) | 2.4 | 0.0% | 0.0 |
| sim10k | 0.6955 | 0.2511 | +0.0 (0.0005) | 2.4 | 1.8% | 0.0041 (0.0049) |
| sim50 | 0.7046 | 0.2554 | +0.009 (0.007) | 1.51 | 17.4% | 0.0565 (0.0693) |
| sam50 | 0.701 | 0.2533 | +0.0055 (0.0063) | 1.88 | 19.5% | 0.0645 (0.0693) |
| sam50_shown | 0.7216 | 0.2619 | +0.0261 (0.01) | 1.21 | 29.4% | 0.0993 (0.0693) |

### ast (n = 811, market log loss 0.6783)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.6813 | 0.2441 | +0.0 (0.0) | 1.15 | 0.0% | 0.0 |
| sim10k | 0.6815 | 0.2442 | +0.0002 (0.0006) | 1.11 | 2.3% | 0.0042 (0.0049) |
| sim50 | 0.6926 | 0.2492 | +0.0114 (0.0072) | 0.47 | 19.2% | 0.0557 (0.0695) |
| sam50 | 0.6885 | 0.2474 | +0.0073 (0.0077) | 0.97 | 25.9% | 0.0655 (0.0695) |
| sam50_shown | 0.714 | 0.2584 | +0.0327 (0.0106) | 0.92 | 33.5% | 0.1102 (0.0695) |

### 3pm (n = 776, market log loss 0.6715)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.6778 | 0.2424 | +0.0 (0.0) | 0.18 | 0.0% | 0.0 |
| sim10k | 0.6781 | 0.2426 | +0.0003 (0.0005) | 0.11 | 1.4% | 0.004 (0.0049) |
| sim50 | 0.6811 | 0.244 | +0.0033 (0.0061) | 0.58 | 21.6% | 0.0516 (0.0694) |
| sam50 | 0.6841 | 0.2456 | +0.0063 (0.0062) | 0.49 | 25.0% | 0.0639 (0.0694) |
| sam50_shown | 0.6947 | 0.2502 | +0.0169 (0.0122) | 0.93 | 35.9% | 0.0999 (0.0694) |

## kalshi

### pts (n = 18,803, market log loss 0.5291)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.5543 | 0.1867 | +0.0 (0.0) | 3.78 | 0.0% | 0.0 |
| sim10k | 0.5543 | 0.1867 | -0.0 (0.0001) | 3.79 | 1.1% | 0.0042 (0.0045) |
| sim50 | 0.561 | 0.1894 | +0.0067 (0.0011) | 3.07 | 14.1% | 0.0535 (0.0637) |
| sam50 | 0.5649 | 0.1907 | +0.0106 (0.0014) | 2.31 | 14.9% | 0.0598 (0.0637) |
| sam50_shown | 0.5757 | 0.1878 | +0.0214 (0.0053) | 2.65 | 31.3% | 0.0971 (0.0637) |

### reb (n = 14,087, market log loss 0.5618)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.575 | 0.1963 | +0.0 (0.0) | 5.39 | 0.0% | 0.0 |
| sim10k | 0.575 | 0.1963 | +0.0 (0.0001) | 5.41 | 1.3% | 0.0041 (0.0045) |
| sim50 | 0.5818 | 0.1986 | +0.0068 (0.0016) | 4.61 | 16.6% | 0.055 (0.0641) |
| sam50 | 0.5866 | 0.2005 | +0.0116 (0.0018) | 3.59 | 17.4% | 0.0637 (0.0641) |
| sam50_shown | 0.594 | 0.1997 | +0.0191 (0.0044) | 3.65 | 29.5% | 0.0866 (0.0641) |

### ast (n = 10,726, market log loss 0.5405)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.5482 | 0.1856 | +0.0 (0.0) | 6.98 | 0.0% | 0.0 |
| sim10k | 0.5482 | 0.1856 | -0.0 (0.0001) | 7.0 | 1.4% | 0.004 (0.0044) |
| sim50 | 0.5556 | 0.1882 | +0.0074 (0.0016) | 5.9 | 18.7% | 0.0544 (0.0622) |
| sam50 | 0.5636 | 0.1913 | +0.0154 (0.0027) | 3.81 | 21.3% | 0.0707 (0.0622) |
| sam50_shown | 0.5845 | 0.1919 | +0.0363 (0.0072) | 3.57 | 30.7% | 0.0892 (0.0622) |

### 3pm (n = 10,791, market log loss 0.5283)

| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |
|---|---|---|---|---|---|---|
| v2 | 0.5294 | 0.1768 | +0.0 (0.0) | 6.75 | 0.0% | 0.0 |
| sim10k | 0.5295 | 0.1768 | +0.0001 (0.0001) | 6.7 | 1.8% | 0.0041 (0.0044) |
| sim50 | 0.5384 | 0.1801 | +0.009 (0.0016) | 4.46 | 20.1% | 0.0545 (0.062) |
| sam50 | 0.5437 | 0.1821 | +0.0143 (0.0022) | 5.31 | 20.3% | 0.0675 (0.062) |
| sam50_shown | 0.5557 | 0.1814 | +0.0263 (0.0061) | 4.81 | 34.0% | 0.0897 (0.062) |

## Verdict by variant (cells where the paired dLL vs v2 clears 2 SE)

| Variant | Better | Same | Worse |
|---|---|---|---|
| sim10k | 0 | 8 | 0 |
| sim50 | 0 | 4 | 4 |
| sam50 | 0 | 4 | 4 |
| sam50_shown | 0 | 1 | 7 |
