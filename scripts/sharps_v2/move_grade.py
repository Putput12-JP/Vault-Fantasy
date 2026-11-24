#!/usr/bin/env python3
"""Sharps V2 Move grade (rule mg-1, docs/sharp-movegrade-prereg.md, spec docs/sharps-v2-movegrade-spec.md): pure functions, stdlib only.

A letter A to D that says how strongly the market moved TOWARD a shown play's side in the 24 hours before the cut, read ONLY from the stored v2f-2
market-move flags of the play (Flag A: Pinnacle's no-vig price at the same line; Flag C: the market's main line, or the books' price on a moneyline)
and the side's direction. A flag fired AGAINST the play gives the "moved against" marker and no letter. Neither flag readable gives no grade.
It describes what the market did. It is not a bet signal and it does not predict results (the in-sample letters do not order them).

Context only (CLAUDE.md): nothing here reads or changes the shown size (flat 1u on NBA, NFL, CBB, none on CFB), the shadow size v2s-1, the evidence
tier, the ladder, sf_rungs, the gates, the locks, Top Reads, SM_GATE or an agree total, and none of those modules reads this one. Pinnacle's limit is
never an input (it rose on almost every play). Nothing after the cut is read: the grade is a pure function of the stored flags block of the play.

Never invent a number: a value that is not stored is None, never 0; a flag state with a missing number is "no grade", never a guessed D. This module
imports flags_v2 for `_dir_sign` and the registered thresholds and NEVER edits it (frozen at the v2f-2 registration).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from sharps_v2 import flags_v2 as F  # noqa: E402

MG_RULE = "mg-1"                                  # a change to any cutoff, input or branch is a new rule id (mg-2) and a new registration
MG_SPEC = "docs/sharps-v2-movegrade-spec.md"
LETTERS = ("A", "B", "C", "D")
SIDES = F.SIDES
STATES = ("toward", "away", "quiet")
# The cutoffs, points, ONE literal table each (docs, tests and the history script read these). Set from the distribution of every started game of the book
# tape (scripts/sharps_v2/move_grade_history.py, tape at origin/main a6b75ea6c404), never from results:
#   M_A, M_C  the C mark: the median absolute 24 hour move (Flag A price; Pinnacle's main line), "more than a typical day's move"
#   X_A, X_C  the A mark: the 95th percentile of the absolute move, at least half a point past the registered flag threshold (T_A, T_C)
# The B mark is the registered flag threshold itself (F.FLAGS_T_A, F.FLAGS_T_C), unchanged and not re-read: B is "a flag fired".
MG_M_A = {"nba": {"ml": 2.0, "spread": 0.5, "total": 1.0}, "nfl": {"ml": 0.5, "spread": 1.0, "total": 0.5},
          "cbb": {"ml": 1.0, "spread": 1.0, "total": 0.5}, "cfb": {"ml": 1.0, "spread": 0.5, "total": 0.5}}
MG_X_A = {"nba": {"ml": 9.0, "spread": 2.0, "total": 2.5}, "nfl": {"ml": 3.0, "spread": 2.5, "total": 2.5},
          "cbb": {"ml": 4.5, "spread": 2.5, "total": 2.5}, "cfb": {"ml": 4.5, "spread": 2.5, "total": 2.0}}
MG_M_C = {"nba": {"spread": 1.0, "total": 1.5}, "nfl": {"spread": 0.5, "total": 0.5},
          "cbb": {"spread": 0.5, "total": 1.0}, "cfb": {"spread": 0.5, "total": 0.5}}
MG_X_C = {"nba": {"spread": 3.5, "total": 4.0}, "nfl": {"spread": 1.5, "total": 1.5},
          "cbb": {"spread": 2.0, "total": 4.0}, "cfb": {"spread": 2.5, "total": 2.0}}
WHY = ("side_unmapped", "no_flags", "flags_unreadable", "no_cutoff")


def _n(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and x not in (float("inf"), float("-inf"))


def _state(blk):
    """The v2f-2 state of a flag block, or None when the block is absent, not an object, or carries a state the rule does not know."""
    s = blk.get("state") if isinstance(blk, dict) else None
    return s if s in STATES else None


def cutoffs(sport, g):
    """-> the marks for this sport and market {m_a, t_a, x_a, m_c, t_c, x_c} (m_c, t_c, x_c are None on a moneyline: it has no line), or None when any
    mark the market needs is missing (an unknown sport or market has no cutoff, never a guess)."""
    tab = lambda t: (t.get(sport) or {}).get(g) if isinstance(t.get(sport), dict) else None
    cut = {"m_a": tab(MG_M_A), "t_a": tab(F.FLAGS_T_A), "x_a": tab(MG_X_A),
           "m_c": tab(MG_M_C) if g != "ml" else None, "t_c": tab(F.FLAGS_T_C) if g != "ml" else None, "x_c": tab(MG_X_C) if g != "ml" else None}
    need = ("m_a", "t_a", "x_a") + (("m_c", "t_c", "x_c") if g != "ml" else ())
    return cut if all(_n(cut[k]) for k in need) else None


def _blank(why, flags_why=None):
    return {"rule": MG_RULE, "letter": None, "against": None, "basis": None, "against_by": None, "a": None, "c": None, "a_pts": None, "c_pts": None,
            "c_kind": None, "c_same_way": None, "c_books": None, "cut": None, "why": why, "flags_why": flags_why}


def c_pts_of(line, g, norm):
    """Pinnacle's main-line move toward the side in points, round(dir x (to - from), 2), from a stored v2.flags.line block; None on a moneyline, on a price
    block, or when the stored from or to is not a number. Never a 0 put in for a missing number."""
    if g == "ml" or not isinstance(line, dict) or line.get("kind") != "line" or norm not in SIDES:
        return None
    pin = line.get("pin")
    if not isinstance(pin, dict) or not _n(pin.get("from")) or not _n(pin.get("to")):
        return None
    return round(F._dir_sign(g, norm) * (pin["to"] - pin["from"]), 2)


def move_grade(flags, g, norm, sport):
    """-> the stored `v2.move_grade` block for one shown play (see the module docstring and spec section 4.2). `flags`: the play's stored v2.flags (or None),
    `g`: ml | spread | total, `norm`: the side's home | away | over | under, `sport`: nba | nfl | cbb | cfb. Pure: reads only these four arguments."""
    if norm not in SIDES:
        return _blank("side_unmapped")
    if not isinstance(flags, dict):
        return _blank("no_flags")
    pin, line = flags.get("pin"), flags.get("line")
    pin = pin if isinstance(pin, dict) else None
    line = line if isinstance(line, dict) else None
    a, c = _state(pin), _state(line)
    if a is None and c is None:
        return _blank("flags_unreadable", flags.get("why") if isinstance(flags.get("why"), dict) else None)
    pts = pin.get("pts") if pin else None
    if a is not None and not _n(pts):                       # a state with no number is garbage: no grade, never a guessed D
        return _blank("flags_unreadable", flags.get("why") if isinstance(flags.get("why"), dict) else None)
    pts = round(pts, 2) if a is not None else None
    cut = cutoffs(sport, g)
    if cut is None:
        return _blank("no_cutoff")
    cp = c_pts_of(line, g, norm) if c is not None else None
    out = {"rule": MG_RULE, "letter": None, "against": False, "basis": None, "against_by": None, "a": a, "c": c, "a_pts": pts, "c_pts": cp,
           "c_kind": line.get("kind") if c is not None and line.get("kind") in ("line", "price") else None,
           "c_same_way": line.get("same_way") if c is not None and _n(line.get("same_way")) else None,
           "c_books": line.get("books") if c is not None and _n(line.get("books")) else None, "cut": cut, "why": None, "flags_why": None}
    if a == "away" or c == "away":                          # any flag fired against the play: the marker, no letter (it wins over a flag fired toward)
        out.update({"against": True, "basis": "against", "against_by": [k for k, s in (("a", a), ("c", c)) if s == "away"]})
        return out
    if a == "toward" or c == "toward":
        if a == "toward" and pts >= cut["x_a"]:
            out.update({"letter": "A", "basis": "a_mark"})
        elif c == "toward" and cp is not None and cp >= cut["x_c"]:
            out.update({"letter": "A", "basis": "c_mark"})
        else:
            out.update({"letter": "B", "basis": "fired"})
        return out
    d_toward = (pts is not None and pts >= cut["m_a"]) or (cp is not None and cp >= cut["m_c"])
    d_away = (pts is not None and pts <= -cut["m_a"]) or (cp is not None and cp <= -cut["m_c"])
    if d_toward and not d_away:
        out.update({"letter": "C", "basis": "drift"})
    else:
        out.update({"letter": "D", "basis": "flat"})
    return out


def mg_of(grade):
    """The `mg` key of a forward log row: a projection of the card's stored v2.move_grade (stored values only). None when the card has no readable block
    (the caller decides between 'not logged' and 'dropped')."""
    if not isinstance(grade, dict):
        return None
    return {"rule": grade.get("rule"), "letter": grade.get("letter"), "against": grade.get("against"), "basis": grade.get("basis"),
            "against_by": grade.get("against_by"), "a_pts": grade.get("a_pts"), "c_pts": grade.get("c_pts"), "why": grade.get("why")}


def bucket_of(grade):
    """The record slice of a grade or of an `mg` projection: a, b, c, d, against or unreadable (a play with no grade). Exactly one."""
    if not isinstance(grade, dict):
        return "unreadable"
    if grade.get("against") is True:
        return "against"
    lt = grade.get("letter")
    return lt.lower() if lt in LETTERS else "unreadable"


def mg_fields():
    """`live.json` v2_plays.move_grade: the rule, the cutoff tables and the legend facts the page reads (never its own constants)."""
    cp = lambda t: {k: dict(v) for k, v in t.items()}
    return {"rule": MG_RULE, "spec": MG_SPEC, "m_a": cp(MG_M_A), "m_c": cp(MG_M_C), "x_a": cp(MG_X_A), "x_c": cp(MG_X_C), "letters": list(LETTERS),
            "shown": True, "context_only": True}
