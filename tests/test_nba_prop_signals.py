"""build_prop_signals.py: fixed tiers, levels, units at a stored price, clustered record."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import build_prop_signals as P


def test_tiers_are_the_frozen_rules():
    assert P.tier_of(4, 3, 0) == 'strong'
    assert P.tier_of(2, 3, 0) == 'lean'          # level 2 cannot be strong
    assert P.tier_of(3, 3, 1) == 'lean'          # any check against drops strong
    assert P.tier_of(3, 1, 0) == 'split'
    assert P.tier_of(4, 1, 2) == 'against'


def test_levels_use_props_sim_cuts():
    assert P.level(0.51) == 1 and P.level(0.54) == 2 and P.level(0.43) == 3 and P.level(0.65) == 4


def test_units_only_at_a_stored_price():
    assert P.units('-110', True) == 100 / 110 and P.units('+150', True) == 1.5 and P.units('-110', False) == -1.0
    assert P.units(None, True) is None and P.units('', False) is None


def test_record_counts_and_expected():
    r = P.Rec()
    r.add(True, 0.6, ('g', 1), -1.0 + 2)      # win at +100
    r.add(False, 0.5, ('g', 2), -1.0)
    n, w, e, se, pn, u = r.out()
    assert (n, w, e, pn, u) == (2, 1, 1.1, 2, 0.0)
