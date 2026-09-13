#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · VACATED SHARE  →  data/vacated_share.json
#
#  MEASURES (does not invent) how much a returning player's OWN volume grows
#  when a higher-ranked same-position teammate LEAVES THE TEAM between seasons —
#  the "the guy ahead of me is gone" bump. This is the roster-DEPARTURE analogue
#  of the within-season injury cascade (build_usage_cascade.py): the cascade
#  reacts to a teammate being OUT for a week; this reacts to a teammate no longer
#  being on the roster at all (traded, signed elsewhere, retired, cut).
#
#  Why a separate model: the injury cascade is measured week-to-week against a
#  player's in-season baseline. A departure is permanent, so its signal lives in
#  the season-over-season change in a player's full-season volume — a different
#  measurement entirely, and the one the projection needs early in a year when a
#  player's history still reflects the room he shared last season.
#
#  Method (nflverse weekly stats, consecutive season pairs S → S+1):
#    · Group each team-season's players by position; rank by per-game volume
#      (carries for RB rushing, targets for WR/TE receiving).
#    · A "room member" needs ≥ MIN_PRESENT games and real starter volume.
#    · For every player p who RETURNS to the same team in S+1 (≥ MIN_PRESENT
#      games), count the real-starter teammates from his S room who are GONE from
#      that team in S+1, split into those ranked ABOVE p and those ranked BELOW
#      him. Direction matters: a departed lead (above) and a departed committee-
#      mate (below) both lift p's volume, but by different amounts — and the RB1
#      who loses his RB2 (a below departure) is exactly the case a higher-only
#      rule would miss. Record his per-game volume RATIO vol(S+1)/vol(S) into the
#      matching direction bucket, keyed (group, p's rank, direction, how many).
#    · To keep the two signals clean, a ratio is only recorded for a direction
#      when NO departure occurred in the other direction (isolated cases); mixed
#      above+below departures are skipped.
#    · Also record the control ratios (same rank, nobody departed either side) to
#      strip out generic year-over-year drift (aging, scheme, pace).
#    · Publish, per bucket, the NET multiplier = median(departed) / median(control),
#      with event counts and IQR — only where enough events support it AND the
#      effect holds up (same side, > 1) across an even/odd season split.
#
#  Also emits `rooms`: the most recent completed season's ranked room per
#  team|group (name, per-game vol, rank), so the frontend can identify which
#  higher-ranked teammate has since left and which bucket the returning player
#  falls in — matched by normalized name, the same id-free join the cascade and
#  role anchor already use.
#
#  Nothing ships to serving unless it clears MIN_EVENTS and the stability gate.
#  A plausible adjustment that doesn't hold up is a no-go (cf. rejected DvP).
#
#  Usage:  python3 scripts/build_vacated_share.py [--since 2014] [--dry]
# ════════════════════════════════════════════════════════════════════════════
import argparse, datetime, json, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "vacated_share.json")

LAST_COMPLETE = 2025   # season whose rooms the frontend diffs the live roster against

MIN_PRESENT = 6            # games needed in a season to count as a real roster piece
MIN_EVENTS = 40            # events required before a bucket publishes a multiplier
RANK_CAP = 3               # rank buckets 1..3 (3 = "rank 4+" prior role)
DEP_CAP = 2                # departed buckets 1, or 2+ higher gone
CLAMP = 3.0                # cap the published net multiplier
MIN_STARTER_VOL = {"rec": 4.0, "rush": 8.0}   # a higher-ranked teammate only "counts" if his role was real
GROUPS = {                 # group → (positions, per-game volume field)
    "rec": ({"WR", "TE"}, "tgt"),
    "rush": ({"RB"}, "car"),
}
VOL_ALIASES = {"car": ("car",), "tgt": ("tgt",)}   # room for renamed columns across seasons


def load(season):
    path = os.path.join(DATA, f"nflverse_stats_{season}.json")
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path))
    except Exception:
        return None


def norm_name(n):
    # Match the frontend's id-free join: lower, strip punctuation and common
    # generational suffixes the market omits (Jr/Sr/II/III/IV/V).
    n = (n or "").lower().strip()
    for ch in ".,'`":
        n = n.replace(ch, "")
    parts = [p for p in n.split() if p not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(parts)


def per_game_vol(rec, vol_field):
    fields = VOL_ALIASES.get(vol_field, (vol_field,))
    vals = []
    for row in rec.get("weeks", []) or []:
        for f in fields:
            v = row.get(f)
            if isinstance(v, (int, float)):
                vals.append(float(v))
                break
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def team_rooms(blob, positions, vol_field):
    """team → ranked [ (norm_name, display_name, vol_pg, games) ] for real room members."""
    by_team = defaultdict(list)
    if not blob:
        return by_team
    for name, rec in blob.items():
        if not isinstance(rec, dict) or rec.get("pos") not in positions:
            continue
        team = rec.get("team")
        if not team:
            continue
        vol, games = per_game_vol(rec, vol_field)
        if vol is None or games < MIN_PRESENT:
            continue
        by_team[team].append([norm_name(name), name, vol, games])
    for t in by_team:
        by_team[t].sort(key=lambda x: -x[2])   # rank by per-game volume, desc
    return by_team


def _departed(members, lo, hi, starter_vol, next_by_name, team):
    """count real-starter room members in rank range [lo,hi) gone from `team` by S+1."""
    n = 0
    for j in range(lo, hi):
        jnn, _jdn, jvol, _jg = members[j]
        if jvol < starter_vol:
            continue
        jn = next_by_name.get(jnn)
        if (jn is None) or (jn[0] != team):   # gone from the league, or now elsewhere
            n += 1
    return n


def measure(seasons):
    # events[(group, rank_bucket)] = { "dep": {dir: {n: [ratios]}}, "ctl": [ratios] }
    events = defaultdict(lambda: {"dep": {"above": defaultdict(list), "below": defaultdict(list)}, "ctl": []})
    pairs = 0
    for S in seasons:
        a, b = load(S), load(S + 1)
        if not a or not b:
            continue
        pairs += 1
        for group, (positions, vol_field) in GROUPS.items():
            rooms_S = team_rooms(a, positions, vol_field)
            # next-season lookup: norm_name → (team, vol_pg)
            next_by_name = {}
            for team, members in team_rooms(b, positions, vol_field).items():
                for nn, _dn, vol, _g in members:
                    next_by_name[nn] = (team, vol)
            starter_vol = MIN_STARTER_VOL[group]
            for team, members in rooms_S.items():
                for k, (nn, _dn, vol_s, _g) in enumerate(members):   # k = 0-based rank in S
                    nxt = next_by_name.get(nn)
                    if not nxt or vol_s <= 0:
                        continue
                    nxt_team, vol_next = nxt
                    if nxt_team != team:      # p himself left — not our subject
                        continue
                    above = _departed(members, 0, k, starter_vol, next_by_name, team)
                    below = _departed(members, k + 1, len(members), starter_vol, next_by_name, team)
                    ratio = vol_next / vol_s
                    rb = min(k, RANK_CAP)
                    bucket = events[(group, rb)]
                    if above == 0 and below == 0:
                        bucket["ctl"].append(ratio)
                    elif above >= 1 and below == 0:
                        bucket["dep"]["above"][min(above, DEP_CAP)].append(ratio)
                    elif below >= 1 and above == 0:
                        bucket["dep"]["below"][min(below, DEP_CAP)].append(ratio)
                    # mixed above+below: skipped to keep each direction's signal clean
    return events, pairs


def _median(xs):
    return st.median(xs) if xs else None


def _iqr(xs):
    s = sorted(xs)
    return [round(s[len(s) // 4], 3), round(s[3 * len(s) // 4], 3)]


def measure_split(seasons, parity):
    ev, _ = measure([s for s in seasons if s % 2 == parity])
    out = {}
    for (group, rb), d in ev.items():
        ctl = _median(d["ctl"])
        if not ctl or ctl <= 0:
            continue
        for direction in ("above", "below"):
            for hb, ds in d["dep"][direction].items():
                m = _median(ds)
                if m is None:
                    continue
                out[(group, rb, direction, hb)] = m / ctl
    return out


def summarize(events, seasons):
    even = measure_split(seasons, 0)
    odd = measure_split(seasons, 1)
    out, rejected = {}, []
    for (group, rb), d in events.items():
        ctl = _median(d["ctl"])
        if not ctl or ctl <= 0:
            continue
        for direction in ("above", "below"):
            for hb, ds in d["dep"][direction].items():
                n = len(ds)
                key = (group, rb, direction, hb)
                if n < MIN_EVENTS:
                    continue
                net = _median(ds) / ctl
                # stability gate: same side and both > 1 across the even/odd split
                e, o = even.get(key), odd.get(key)
                if e is None or o is None or not (e > 1.0 and o > 1.0 and net > 1.0):
                    rejected.append((key, n, net, e, o))
                    continue
                net = max(1 / CLAMP, min(CLAMP, net))
                out.setdefault(group, {}).setdefault(str(rb), {}) \
                   .setdefault(direction, {})[str(hb)] = {
                    "mult": round(net, 3), "n": n, "iqr": _iqr(ds),
                    "ctl": round(ctl, 3), "split": [round(e, 3), round(o, 3)],
                }
    return out, rejected


def emit_rooms(season):
    """Most recent completed season's ranked rooms, for the live diff."""
    blob = load(season)
    rooms = {}
    for group, (positions, vol_field) in GROUPS.items():
        for team, members in team_rooms(blob, positions, vol_field).items():
            starter_vol = MIN_STARTER_VOL[group]
            lst = []
            for rank, (nn, dn, vol, games) in enumerate(members, start=1):
                lst.append({"name": dn, "nkey": nn, "vol": round(vol, 2),
                            "rank": rank, "starter": vol >= starter_vol})
            if lst:
                rooms[f"{team}|{group}"] = lst
    return rooms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2014)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    seasons = list(range(args.since, LAST_COMPLETE))   # pairs S→S+1, last pair 2024→2025
    events, pairs = measure(seasons)
    summary, rejected = summarize(events, seasons)
    rooms = emit_rooms(LAST_COMPLETE)

    print(f"[vacated] season pairs {args.since}→{args.since + 1} .. "
          f"{LAST_COMPLETE - 1}→{LAST_COMPLETE}  ({pairs} pairs)")
    LABELS = {"rec": "receiving (tgt)", "rush": "rushing (car)"}
    RANK = {"0": "rank1", "1": "rank2", "2": "rank3", "3": "rank4+"}
    DIRW = {"above": "higher", "below": "lower"}
    for group in ("rec", "rush"):
        g = summary.get(group, {})
        print(f"── {LABELS[group]}")
        if not g:
            print("     (no bucket cleared MIN_EVENTS + stability — signal too thin/unstable to ship)")
        for rb in sorted(g):
            for direction in ("above", "below"):
                for hb in sorted(g[rb].get(direction, {})):
                    c = g[rb][direction][hb]
                    cnt = "1" if hb == "1" else "2+"
                    who = f"{cnt} {DIRW[direction]} left"
                    print(f"     {RANK[rb]:6s} · {who:16s} → ×{c['mult']:.3f}  "
                          f"(n={c['n']}, IQR {c['iqr'][0]:.2f}–{c['iqr'][1]:.2f}, "
                          f"ctl {c['ctl']:.2f}, split {c['split']})")
    if rejected:
        print(f"── rejected buckets (thin or failed even/odd stability): {len(rejected)}")
        for key, n, net, e, o in rejected:
            es = f"{e:.2f}" if e is not None else "—"
            os_ = f"{o:.2f}" if o is not None else "—"
            print(f"     {key} n={n} net={net:.2f} even={es} odd={os_}")
    print(f"── rooms emitted for {LAST_COMPLETE}: {len(rooms)} team-groups")

    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "since": args.since, "last_complete": LAST_COMPLETE, "min_events": MIN_EVENTS,
        "note": ("net own-volume multiplier (vs same-rank control) when N higher-ranked "
                 "same-position teammates leave the team between seasons; measured from "
                 "nflverse weekly stats. `rooms` = last completed season's ranked rooms "
                 "for the live roster diff."),
        "buckets": summary, "rooms": rooms,
    }
    if args.dry:
        print("[vacated] --dry: not written"); return
    json.dump(payload, open(OUT, "w"))
    print(f"[vacated] wrote {OUT}")


if __name__ == "__main__":
    main()
