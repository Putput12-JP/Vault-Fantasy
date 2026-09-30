# What makes this model different

Written 2026-09-30, after the week 1-3 backtests. Anyone can ask Claude for "an NBA betting model" and get
roughly what we built in weeks 2 and 3: team ratings, a minutes x rate prop projection, a probability curve.
That part is a commodity. Our own results prove it cannot be the edge:

- The game model matches the closing line and adds nothing to it (t = 1.2).
- The prop model is **less accurate than every market price** on its own. Betting model vs price loses.
- Everything that did make money came from somewhere other than model quality:
  - **Where** we bet: Kalshi player props, where YES is overpriced in every price bucket.
  - **When** we bet: the model "beat" ESPN's opening lines at 57 to 59% ATS because the open predated the
    injury news. The close then moved toward the model 466 times vs 229.
  - **How** we combine: the model adds real information on top of a price (t = 3 to 6 on Kalshi), as long as
    the market does most of the work.

So the plan is to compete on the things a one-off model does not have: venue, timing, execution, data we
own, and the user's own judgement. In order of expected value:

## 1. Bet where retail sets the price, not where sharps do

Pinnacle and the big books' main lines are efficient; we could not beat them. Retail-priced markets are
not: Kalshi prop YES hits 2 to 5 points below its price all season, in every stat. Next targets with the
same structure: Polymarket props, pick'em apps with flat payouts (PrizePicks, Underdog; the NFL feed
already covers them), exchange ladders. **Test:** track the overs bias weekly from opening night; stop the
moment it closes.

## 2. Be the order book, not the taker

Kalshi's taker fee (0.07 x p x (1 - p), up to 1.75 cents a contract) eats most of a thin edge, and the
3-pointer strikes only trade about 30 contracts in the 30 minutes before tip. A model tells you what to
bet; almost nobody builds how to get filled. Resting NO orders on over-bid YES ladders collects the bias
as the maker instead of paying to cross it. **Test:** replay the trade tape: would a resting order at our
fair price have filled, at what size, and was the fill adversely selected (did the fills that happened lose
more than the ones that didn't)? Check Kalshi's current maker fee schedule before sizing.

## 3. React to news in minutes, not hours

The biggest mispricing we measured was a price that had not caught up with the injury report yet. The
report now posts every 15 minutes, and the minutes model knows exactly who gains: plain recent minutes
under-project a same-position teammate by 1.4 minutes, and the model fixes that. Pipeline:

1. poll the report (and later, team and beat-writer feeds) every few minutes on game days
2. re-project every affected teammate the moment a status changes
3. compare with every live price (Kalshi, Polymarket, Pinnacle, pick'em apps)
4. alert on the gaps, logged with the time the news broke and the time each venue moved

A model built once in a chat has no clock. **Test:** from the logs, measure how long each venue takes to
move after a status change, and the edge available inside that window.

## 4. Own timestamped history nobody else has

The hardest part of week 1 was that free history has no timestamps (ESPN opens) or is missing whole
months (sportsbook props Dec to Mar). From opening night we snapshot every venue's prop and game prices
every few minutes, plus every injury report and every lineup. After one season we will hold the only
honest record of "what the price was when the news broke" for our markets. No one can download that, and
no one asking Claude cold can backtest what we can.

## 5. Blend with the market, never replace it

The shippable number is `fair = market + a measured nudge from the model`, with the weights fit on
earlier data only. That is what survived out of sample (Kalshi 3-pointers: +9.4% vs +5.1% for the bias
alone). Most DIY models bet their own number against the market and bleed slowly. Our other guard is
discipline, which protects capital rather than beating competitors:
- pass/fail rules fixed before looking at results
- tests only on held-out data
- ROI per contract
- a "bias alone" baseline for every edge

## 6. Put the human in the loop (the Minutes Lab)

Models read box scores. They do not read "minutes restriction", a coach's rotation comment, or a
player's rest pattern. The Minutes Lab turns that knowledge into numbers: change a player's minutes and
every stat reprices. The next step is to show the **live price and the edge** next to each projection,
so a minutes judgement becomes a bet in seconds. That is also a Vault product feature nobody else ships.

## 7. Price the structure, not just the player

Kalshi's ladders give a full distribution per player, sportsbooks give one line, and pick'em apps price
every leg as if it were independent. Inconsistencies between them need no better model:
- a player's ladder vs his book line
- PRA vs the sum of its parts
- teammates who share usage (negatively correlated) sold as independent legs

The NFL work found a +22% mispricing of this kind (a QB and his WR1 both going over). **Test:** measure
the teammate points correlation and the ladder-vs-line gaps on the snapshot data.

## What we will not compete on

- More model complexity: gradient boosting, neural nets, 3,000 features. Everyone has these, and our
  own tests say accuracy is not the bottleneck.
- Headline win rates or "accuracy".
- Anything that only works against an untimestamped opening line.

## Revised week 4

1. Live snapshot pipeline on game days (all venues, every few minutes) from opening night. This is the
   data advantage, and it compounds only if it starts now.
2. Injury news re-pricer with alerts and venue reaction times.
3. Shadow the Kalshi 3-pointer NO blend, the overs-bias tracker, and a maker-order simulation.
4. Live prices and edges in the Minutes Lab.
