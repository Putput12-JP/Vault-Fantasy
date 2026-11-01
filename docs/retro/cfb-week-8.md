# CFB week 8 retro (2026-10-26): the model bounced to 9-6 on 5+, still no proven edge, and JP+ per-game numbers were not recorded

Numbers come from `data/cfb_scoreboard.json` (`games` rows), recomputed with the same rules as the scoreboard: weeks 4+, FBS vs FBS, a lean is the side of the ESPN recorded open our projection is on, graded against the open unless it says close. Recomputing week 7 this way reproduces the published scoreboard exactly (25-25-3, 5+ 7-11-1), so the week 8 figures below are comparable. Previous retro: `cfb-week-7.md`.

## JP+ for week 8

Our scoreboard job did not record any JP+ number for week 8: `data/jpplus_games.json` holds weeks 1 to 7 only, and every run since the weekend logged `JP+ fetch skipped: HTTPError HTTP Error 429: Too Many Requests` (latest 2026-10-26 07:55 UTC). So there is no game-by-game, pre-kickoff-verified JP+ line for week 8, and the scoreboard (which needs every number present) stops at week 7. The fetch needs a backoff or wider spacing before the next slate.

JP+'s own page (`jpplusratings.com/picks/spreads/?week=2026-8`, read 2026-10-26) does show its week 8 results. These are JP+'s numbers graded by JP+ to its canonical opening spread, entered here as reported, not our grading:

| JP+ week 8, as reported | record |
|---|---|
| All completed predictions | 31-25 (55.4%) |
| All 5+ disagreements | 10-9 (52.6%) |
| Selection engine | 8-9 (47.1%), -8.6u |
| Season, all / 5+ / selection | 263-181 (59.2%) / 105-74 (58.7%) / 70-46 (60.3%) |
| Average miss, 440 games | JP+ 11.78, open 11.46, close 11.23 |

The season lines are not last week's report plus this week: all went from 230-158 to 263-181 (31-25 this week, so 2 games differ) and 5+ from 93-62 to 105-74 (10-9 this week, so 12 wins and 12 losses were added to earlier weeks beyond it). JP+ has restated earlier weeks, so the old season figures in `cfb-week-7.md` are not comparable to these.

The page lists only the 17 selection picks game by game. Each carries an "added to picks" time between Oct 18 and Oct 20, before its kickoff, so those 17 lines were published ahead of the game. The rest of JP+'s 56 games are not visible, so they cannot be joined to ours.

On those 17 picks, 14 are games on our board. We lean the same side as JP+ on 10 and the opposite side on 4 (Mississippi State, Illinois, Cincinnati, Central Michigan). JP+ went 4-6 on the 10 shared sides (Colorado Oklahoma State side, TCU, Northern Illinois, Tulsa, Pitt at Miami and Memphis lost; Colorado State, Wisconsin, Texas State and Kansas won) and 3-1 on the 4 where we were on the other side. The results are JP+'s own labels at its own open, ours use ESPN's open, and the sample is tiny, so read it as "no week 8 evidence that JP+'s selections beat ours." Where we agreed with JP+ we lost most of the same games (Colorado, Pitt, TCU).

Headline comparison: JP+ 5+ 10-9 against our 9-6 (different pick sets and different opens). JP+ average miss is 11.78 on 440 games against our 12.74 on 262 (different games, season-long, not comparable to the decimal).

## Scorecard, week 8 (50 finished games on our board, none pushed)

| | all games vs open | 3+ | 5+ from the open | avg miss |
|---|---|---|---|---|
| Our model | 25-24 (51.0%) | 13-12 | 9-6 (60.0%) | 11.34 |
| Previous model (v1 shadow) | 25-24 (51.0%) | 10-12 | 7-8 | 11.92 |
| JP+ (own report, own open, 56 games) | 31-25 (55.4%) | | 10-9 (52.6%) | |
| Opening line | | | | 11.17 |
| Closing line | | | | 10.88 |
| Our official picks (log, restated) | 6-6-1 (50.0%) | | | |

Official picks as logged at the time were also 6-6-1. Season restated: 46-44-4 (51.1%); as logged 46-48-5.

Season on our board, weeks 4 to 8 (262 games):

| | all games | 3+ | 5+ | avg miss |
|---|---|---|---|---|
| Our model | 144-111 (56.5%) | 88-72 (55.0%) | 57-49 (53.8%) | 12.74 |
| Previous model | 141-114 | 69-63 | 42-43 | 12.68 |
| Opening line | | | | 12.18 |
| Closing line | | | | 11.69 |

Week 7 to week 8 on 5+ went from 7-11-1 to 9-6. By week: 13-17, 14-8, 14-7, 7-11, 9-6.

## Did we succeed?

A little better than last week, and it is still inside noise. 9-6 on 15 picks is 60% with a wide interval; the 5+ season record of 57-49 (53.8%, n=106) is barely above 50% and its break-even at -110 is 52.4%. The all-games lean record of 56.5% on 255 games is the steadier read and has held between 56% and 58% all season.

Flag for close monitoring: the 5+ record improved from 48-43 to 57-49 (52.7% to 53.8%). Sample is 106 picks, one new week of 15, so this is not evidence of a fix. Nothing about the model changed between week 7 and week 8 that would explain it.

Wins: Alabama over Texas A&M (we had Alabama by 13.7 against an open of 2.5, closed 13.5), Navy and Wyoming against stale opens, Liberty at Kennesaw State (we had 14.6 against an open of 8.5, final 28), Duke at Virginia, Ole Miss at Texas, Louisiana at Southern Miss.

Losses: Colorado at Oklahoma State (we had OSU by 4.8 against an open of 14.5, final 33), Pittsburgh at Miami (FL) (29), Virginia Tech at Clemson (we liked Clemson by 6.7 against an open of -1.5, Virginia Tech won by 4), Indiana at Michigan, New Mexico State at Sam Houston, Eastern Michigan at Ohio. Same pattern as week 7: the misses are mostly the model fading a big favorite who then won big (Colorado, Pittsburgh).

## Closing line value

5+ picks entered at the open beat the close by 2.10 points on average in week 8 (15 picks, 60.0% beat it). Week 7 was 1.87 points (19 picks with a 5-point edge on this definition, 68.4%). The scoreboard's season figure through week 7 was 1.55 points and 66.4% on 113 picks. The beat-the-close rate is lower this week even though the average is higher, so two or three large moves are carrying the average. On all 49 games with any lean the average is 0.56 points and 46.9% beat the close, so the CLV is concentrated in the big-edge picks and does not extend to the whole slate.

Graded against the close instead of the open, week 8 5+ is 8-7 (week 7 was 7-12). As always, the close takes back part of the result.

## Watch items carried from week 7

1. **Projections too narrow.** Standard deviation of our projected margin is 7.9 in week 8 (8.2 over weeks 4 to 8) against 11.5 for the open over the season. Slope of the final margin on our projection: 0.99 in week 8, 1.37 over weeks 4 to 8 (1.45 through week 7). The week 8 slope is closer to 1, which is what a well-sized projection would show, but one week of 50 games has a large error on a slope, so this is not a reading that the width is fixed. The v1 shadow is 10.5 wide with slope 1.03.
2. **Weight on our disagreement with the market.** Regressing final minus open on our edge: 0.25 in week 8, 0.24 over weeks 4 to 8, 0.24 through week 7. Unchanged. This is the number to move, and it has not moved.
3. **Pick is the favorite.** Week 8 was 4-1, taking the live record from 5-6 to 9-7 (n=16). The week 7 watch was that this subset looked worse than the rest; one 4-1 week does not clear it or confirm it. Underdog-side picks are 48-44 over the season (n=92). Keep watching, change nothing.

## What this changes

- **Model/data:** nothing. No change to the model, the pick rule or any stored row this week, so there is no old-number versus new-number table and no historical restatement to run.
- **UI:** nothing.
- **Open item:** JP+ recording is down on a rate limit. Until it is fixed the scoreboard cannot publish week 8 or later head-to-head weeks. This is a tracking fix, so when it is done the week 8 gap stays a gap (no backfill after kickoff) and the note on the scoreboard should say so. `data/jpplus_reported.json` has not been updated for week 8; that is a data edit and is not part of this doc.

## Limits

- 50 games and 15 five-plus picks cannot separate a 54% model from a 50% one. At 106 picks the 95% interval on 57-49 is roughly 44% to 63%.
- The open is ESPN's recorded open, which is stale for some games (Alabama 2.5 against a close of 13.5, Oklahoma State 14.5 against 12.5). Stale opens inflate both the wins and the losses on the largest edges.
- Records for weeks 4 to 6 were restated with the current model in the week 7 retro, so only weeks 7 and 8 are clean forward weeks (16 picks on 5+ combined, 7-11-1 then 9-6, so 16-17-1).
