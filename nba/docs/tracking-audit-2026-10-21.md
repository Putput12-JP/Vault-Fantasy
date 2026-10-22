# Tracking audit, 2026-10-21

Question: is everything the Vault NBA recorder is supposed to log actually logged, settled and shown? Read at 14:30Z to 17:40Z on Oct 21 from the `nba-data` branch, ESPN's scoreboard and summaries, and the board on `nba-live`. Rerun any time with `python3 nba/scripts/audit_tracking.py` (read-only, stdlib, no git needed). Fixes: `python3 nba/scripts/check_tracking_audit.py` proves each one.

Scope: three regular-season games are final (BOS @ DET 401909088, PHI @ NY 401909089, OKC @ SA 401909090). Oct 21's eleven games had not tipped (first tip 23:00Z), so **nothing about Oct 21 settlement could be checked**. Rerun the audit tomorrow.

## Findings, worst first

| # | Finding | Evidence | Status |
|---|---|---|---|
| 1 | **The recorder watchdog was blind.** It read "the last two folders" of `snapshots/`, but the recorder also writes closing prices into folders for days that have not happened yet (no `polls.jsonl`). From Oct 19 22:30Z it saw no polls and said "recorder healthy" (runs at 22:31Z and 01:27Z, both "healthy") while the ledger failed every poll. The issue opened at 06:21Z Oct 20, 11 h 20 m after the crash began (19:01Z), and only because a new day folder had appeared. Right now folders 10-22 and 10-23 exist, so it is blind again. `build_data_health.py` had the same flaw. | Replayed the old script against `nba-data` at 22:30Z Oct 19: "healthy". New script: reports the ledger, failing since 19:01Z. | **Fixed** |
| 2 | **The watchdog runs every 2.5 to 5 hours, not every 30 minutes** (GitHub throttles `*/30`). Runs on Oct 19 to 20: 18:10, 22:31, 01:27, 06:21, 11:55, 16:14, 20:03Z. Detection is hours late even when it sees. | `gh run list --workflow watch-recorder.yml` | Open: the in-recorder flags (Data Health) are the fast path; the issue is the slow path |
| 3 | **A merge reaches the recorder only when its run restarts.** Run 39610337348 started 14:39Z on commit 2a04690, the main commit at its 13:42Z queue time. That commit has no `record_held` or `held_bets_record` (PR 206, 209). Live `track.json` at 17:24Z has no `held_days` or `held_bets_days` key. A pending run on 1ec488a starts at the hand-off (about 20:09Z) or when the current run is cancelled. | `gh api .../contents/nba/scripts/ledger.py?ref=2a04690`: 0 matches; `b6e9c6d`: 4 | **Visible now**: `status.json` carries `code`; Data Health prints the commit; the watchdog notes a recorder behind main. Restart is the user's call |
| 4 | **ESPN corrects box scores after the final; the recorder froze the first read.** OKC @ SA: stored Alex Caruso 7 reb / 2 stl, Jared McCain 3 reb; ESPN now says 6 / 1 / 2 (5 cells, 2 players). The first read was cached forever. | Stored `results/401909090.json` vs fresh summary; the other two games match | **Fixed**: every finished game is re-read hourly for 36 h, then every 12 h to 72 h; a change rewrites the box, re-grades bets, and is listed in `track.json` `box_changes` and in Data Health |
| 5 | **Silent record failures.** `settle()` swallowed errors from the simulation, props simulation, held, Novig, closing price and signal records (a `print` only). A record could stop updating with the recorder showing healthy. | Code read | **Fixed**: named in the poll record (`ok:false`, which feeds the 3-poll Data Health flag and the watchdog) |
| 6 | **A game that never settles was invisible.** No flag for a game with no final box score, or bets open, long after tip. | Code read | **Fixed**: `unsettled` flag at 8 h past tip |
| 7 | **Data Health injuries column read "none" for every game.** The report writes `AtlantaHawks`, the join looked for `hawks` as a whole word. | Status coverage on Oct 21: all 11 games `-` | **Fixed**: now 9, 4, 4, 4, 8, 5, 6, 7, 10, 6, 9 players (sum 72 = the report's 72 rows) |
| 8 | **80% of tonight's 3%+ edges are held by the roster guard.** Board at 14:39Z, 11 games in the 24 h window: 1,761 edge candidates; 257 logged (15%), 1,431 held (team), 55 (player), 18 (returning). 7 of 11 games log nothing. 128 of 161 GO/WATCH candidates are held. | `pricing.price_board` on the live board | Design, not a bug. Covered by the held groups (below) |
| 9 | **12 markets show a Lean on the page and are never tracked** (stl, blk, tov, sb, fgm, fga, ftm, fta, tpa, oreb, dreb, pf): 593 of 1,590 board lines in the window (37%). `pricing.price_board` skips them on purpose (no backtest). | Board count | Not changed; a shadow log for them is a follow-up |

## Games, Oct 20 (all final)

| Record | Should exist | Exists | Gap | Cause | Status |
|---|---|---|---|---|---|
| Box score `results/<id>.json` | 3 | 3 | OKC @ SA differs from ESPN now in 5 cells | No re-read | Fixed (#4); heals on the first run with this code, within 72 h of tip |
| Shadow bets (cube, `bets/`) | 0 by design | 0 | none | All 6 teams held (replay: 24,301 + 14,596 + 14,350 held candidates, 0 logged) | As designed |
| Held props group (`held_days`) | 3 games | 0 in live `track.json` | key absent | Run on 2a04690 (#3) | Previewed with the new code on the replayed data: BOS @ DET 61 props 32W-29L (replay), PHI @ NY 55 props 26-29, OKC @ SA 68 props 37-31 (36-32 on the uncorrected box; the McCain rebound correction flips one) |
| Held GO/WATCH plays (`held_bets_days`) | 3 games | 0 in live `track.json` | key absent | Same | Previewed: 79 plays 44W-35L +2.18u (BOS @ DET), 76 plays 41-35 +4.06u (PHI @ NY), 75 plays 44-31 +8.43u (OKC @ SA). These are rows the ledger would have logged, one unit each, at the stored entry price. Not bets, not in the season record |
| Biggest gap (`gap_days`) | 3 | 3 | none | | OK: Jenkins pts over 7.5 L (3), LeBron James ast under 7.5 W (7), Vassell reb over 3.5 L (3); all match the box |
| Props simulation (`psim_days`) | 0 | 0 | by design | Every prop is held, held props are left out of the model comparison | As designed |
| Game Simulation (`sim_days`) | 3 games x 3 environments | 3 x 3 | none | | OK. BOS @ DET came from the replay |
| Minutes Lab (`minutes_days`) | every player who played | 68 played + 20 did not play | none: every player who played has a row (22, 19, 27 of 22, 19, 27) | | OK. 31 rows are replay rows |
| Novig paper (`novig_days`) | 0 | 0 | none | Novig paper skips held teams | As designed |
| Signals and types | all alerts | 321 alerts for Oct 20; all 321 have a result | 113 have no CLV (no Pinnacle close at that line or no fair) | By design in `grade_alert` | OK. Counts equal the `signals.json` files (the per-bet "behind" roll-up aside) |
| Wire | 7 venues | 7 | `five` events: 1 (PHI @ NY) | Lineup changes only | OK |
| Preseason separation | 0 preseason in the season record | 0 | none | | OK: 67 preseason games, 3,091 bets, no preseason id in any season record |

Totals: cube 597 = `bets/2026-10-21.json` 597 = `track.n` 597 (all open, tonight's slate); preseason 3,091 = the 14 preseason files. Book names in the bets: Kalshi, DraftKings, Pinnacle, PrizePicks, Underdog, Sleeper, Polymarket (one spelling each; `Draft Kings` still appears in the raw ledger meta, 136 keys, and merges on read). No player id with two names, no name with two ids; every team code is ESPN's (GS, NY, SA, NO, UTAH, WSH, PHX). The page lists the latest 600 bets, so once the count passed 600 (602 at 14:56Z) distinct picks are counted on 600 of them.

## Polls (Oct 20 and Oct 21 so far)

| Source | Polls | ok:false | Longest gap between good polls | Notes |
|---|---|---|---|---|
| kalshi, espn, pinnacle, action, polymarket, injuries, sleeper, tape, novig | 188 (Oct 20), 63 (Oct 21 by 10:56 ET) | 0 | 15 min | No frozen feed: longest run of unchanged polls 3 (Pinnacle) |
| prizepicks, underdog | 188 | 1 each | 19 min | One 403 each at 02:21 ET Oct 20 (geo block) |
| lineups | 188 | 53 (Oct 20), 37 (Oct 21) | 15 min | All 403 "not posted yet", between 21:xx and 06:00 ET. By design; the watchdog now counts it only while a game is still to tip today |
| ledger | 188 | **128** | 10 min | `'NoneType' object is not subscriptable`, 04:01Z to 21:44Z Oct 20 (plus 56 in the Oct 19 folder from 19:01Z): 184 polls, fixed by PR 205 |

Every final game had a good poll of every source 0 to 8 minutes before its scheduled tip (lineups 23 min for OKC @ SA); no ledger poll for BOS @ DET (crash). ESPN lists OKC @ SA at 01:50Z after the game; Pinnacle, Action and the recorder had 01:30Z all day, so prices from 01:30Z to the actual start were not recorded. Cadence inside 3 h of a tip was 12 polls an hour; outside, 4 to 6.

## Failure visibility: does each mode now fire?

| Failure | Before | Now |
|---|---|---|
| Ledger stage crashes | Data Health flag after 3 polls (PR 205); watchdog blind (#1) | Both |
| A settle record fails (sim, props sim, held, Novig, closes, signals, box refresh) | Job log only | Poll `ok:false`, so the same flag and watchdog |
| Game not settled 8 h after tip | Nothing | `unsettled` (bad) |
| Box score corrected | Nothing | `box_corrected` (note) with old and new numbers |
| Recorder silent for 3 h | Data Health "Late/Down" only when someone looks | Watchdog issue |
| Recorder on old code | Nothing | Commit shown on Data Health; watchdog line |
| Source down 6 polls | Watchdog (blind when 2 future folders exist) | Watchdog on the last two days that have polls |
| Game with no Minutes Lab or simulation rows | PR 205 flags | Unchanged; watchdog now issues on them |

## Could not verify

- Settlement of any Oct 21 game (none had tipped); open bets after a final, overtime, and late-night day-boundary handling beyond OKC @ SA's 01:30Z tip (it settled under Oct 20 correctly).
- Whether ESPN's current box is the NBA's final: the NBA CDN would not answer from here.
- That the Props page's JavaScript would show the same Bet/Lean/GO as `pricing.py` on today's board (the parity checks exist but I did not run the page).
- How many of the 593 untracked extra-market lines the page shows as Lean (needs the page's pricing).
- Lines that appeared and vanished between two polls, or edges that existed only before the 24 h window.
- 12 `unmapped` pick'em or Polymarket lines (Polymarket 3, Underdog 9 on the board) and the skipped PrizePicks/Underdog markets (fantasy score, two-pointers, dunks, double doubles): they are counted, not identified.
- Held props and plays use the model files on hand at the replay, not the recorder's files at the time.
