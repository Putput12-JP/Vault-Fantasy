# Sharp Money V2: user guide

Open **vaultfantasy.com/sharp-money**. On a computer you get a sidebar. On a phone you get tabs along the bottom. The page opens on **Plays**. The "Updated N ago" badge shows how fresh the data is (it refreshes about every 10 minutes).

## The one idea

Following where big money went is usually too late. By the time you see it, the price has moved. So V2 asks a different question: **is a sportsbook still offering a better price than the market says is fair?**

It checks two independent "fair prices":
- **Pinnacle**, the sharpest sportsbook.
- **The exchange**, meaning Kalshi and Novig, where people trade against each other.

A price only counts when it beats **both**.

## Plays

Three lists:
- **Plays**: the price clears every check. This is the short list.
- **Watch**: beats one fair price but has no second price to confirm it. Do not treat it as a play.
- **Passed**: looked good against one price, then failed a check. The reason is written on the row.

At the top is the **V2 play record**: the count (W-L), units, ROI and CLV of every play V2 has logged. Each play is saved once, the first time it appears, then graded when the game ends. It reads 0-0 until the first games finish, and it needs about 100 settled plays before it means much.

Each play card shows team logos (or the player's photo for props), the pick in large type, and:
- **You pay**: the price you can get, and at which book.
- **Pinnacle fair** and **Exchange fair**: what each says the real chance is, and how much better your price is (the edge).
- **Worst-case edge**: the smaller of the two edges. Plays are ranked by this, so the list is conservative.
- **A price bar**: the white tick is what you pay, the green dots are the two fair prices. The green stretch between them is your edge.
- **Logged**: a chip that shows whether the play is in the record and how it ended.
- **Cautions** in yellow, for example "QB props have lost" or "this line is more than 48 hours out".
- **How that market has done** so far, and how long the book has been behind Pinnacle.

Use the **All / NFL / CFB / NBA** control to filter. Tap a card to open that game.

The checks, in plain words: the price is at a US sportsbook (not a pick'em app), both fair prices exist and agree, you beat both by at least 2%, the edge is not suspiciously huge (over 10% has lost money), and the other side of the same bet is not also flagged.

## Signals

A report card for each old signal (Pinnacle line move, money vs bets, +EV at a book, and so on). For each you see the record, whether it beat the price it was taken at, closing-line value (CLV), and units with and without the five biggest wins.

The label tells you how far to trust it:
- **Trust**: 100+ games and clearly beating the price. Nothing has reached this yet.
- **Watch**: looks fine, not enough proof.
- **Ignore**: winning less than its price says it should.
- **Too few**: not enough games to say anything.

Sharp accounts (Polymarket) are shown last, **for context only**. They never rank a play.

## Record

- **V2 plays**: every play is saved once, the first time it appears, with the price and both fair prices it showed. It is then graded. It starts empty and fills in as games finish. Until it has about 100 settled plays, treat a play as a better price, not a proven edge.
- **Every rule, graded**: the same table for all signals.
- **Props and CLV**: how prop calls did against the exchange close. This replaced an older figure that mostly repeated each call's own claim.
- **Models**: how the Vault model did against the closing price (no better than the market so far).

## On a game page

Open any game and scroll down for:
- **Plays on this game**: what V2 thinks of it, in one line.
- **Who is behind**: each US book's number, when it last changed, and whether it differs from Pinnacle.
- **Spread key numbers** (NFL): a half point across a 3 or a 7 is worth much more than other half points.

## Props page

The three CLV tiles now use the exchange close. The older +2.7% looked good but was measured against the same price that raised the call. Against the exchange close it is about +0.1%.

## How to use it

1. Open **Plays**. If it says "Nothing clears every gate", that is the right answer. Skip the day.
2. Check the price is still there before you bet. Prices move.
3. Do not wait for a book to catch up. In our data (one weekend of college football and a few NBA games), US books followed a Pinnacle move only 10 to 17% of the time, and under 10% within an hour.
4. Look at **Record** now and then. It is the honest scoreboard.

## Words

- **Fair price**: the chance with the sportsbook's fee removed.
- **Edge**: how much better your price is than fair. +3% means you pay 3% less than fair.
- **CLV (closing-line value)**: did you get a better price than the final price before the game? It is the fastest test of skill.
- **Exchange close**: the final Kalshi and Novig price before kickoff.

## Limits

- It is about 8 days of history. Treat every record as early.
- A play is a better price, not a prediction. It will still lose often.
- Nothing here is financial advice. The tracker scores flat 1 unit bets only so the numbers are comparable.
