# The prop model as a tilt on the market price

The Sharp Money Props page prices off the market (Pinnacle power-devig, or a liquid
Kalshi strike). `VaultPropModel` never feeds it. Question: does the model add anything
on top of the price, and if so how do we use it?

```
logit P(side) = logit(p_market) + c * ( logit(p_model) - logit(p_market) )
```
c = 0 is the market, c = 1 is the model. Scripts: `scripts/fit_prop_offset.py` (Vault's
settled ledger), `scripts/backtest_prop_offset_espn.py` (ESPN BET 2024-25, open + close).

## What was measured

| Test | Result |
|---|---|
| Vault ledger, wk 1-5 2026 (n=2,457, book consensus at the open) | pooled c = +0.35 (se 0.08); walk-forward log-loss 0.6863 -> 0.6825 (z 2.5) |
| ESPN BET 2024-25 (n=29k snapshots), out-of-sample | pooled c = +0.14; walk-forward skill +0.09% at the open (z 1.9), +0.02% at the close |
| Betting the tilt at ESPN's price | ROI negative at every EV threshold (the raw model's is too) |
| Open -> close line move, same-line snapshots | mean CLV for the model's side grows with disagreement: +0.03 pts (|d|<0.1), +0.39, +0.92, +1.56 pts (|d|>0.5); same sign both seasons (+1.29 / +1.01 pts at |d|>=0.25) |

## Reading it

- The model is NOT an edge against a posted price. As a probability it adds about 0.1% of
  log-loss skill over a book's own no-vig number, and it loses money when bet on EV.
- It IS a leading indicator: the market drifts toward the model's side between the open
  and the close, and the drift scales with how far the model disagrees. That is CLV, and
  the CLV test does not use outcomes, so the model's in-sample calibration cannot inflate it.
- So the right job for the model on the price engine is a SMALL tilt (c around 0.15-0.35)
  and a timing/confirmation signal on an early price, not an override and not a veto.
- `pass_yd` / `pass_att` / `pass_cmp` carry no usable tilt (c <= 0, within noise).

## Limits

ESPN BET is one soft book, not Pinnacle; its "open" is stale compared with a sharp open,
so the CLV above is probably an upper bound for the live page. The shipped model's
calibration was fit through 2025 (the projection itself is walk-forward), so the
probability scores flatter the model slightly. The ledger is the model's chosen side only.

## Live logging

`scripts/prop-model-probe.mjs` computes the model's number with the same code the Best
Bets builder uses (imported, not copied). `track-prop-plays.mjs` stores it on each newly
logged play as `model: { proj, p, d, games, roleMult }` (p = model P on the called side,
d = logit gap to the fair price). Nothing reads it for a decision yet. Once plays settle,
score Pinnacle-fair-only against fair + tilt on this ledger before changing any stake.
