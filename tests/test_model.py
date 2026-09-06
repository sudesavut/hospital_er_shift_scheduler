"""Tests for role-priority weighting in model.py."""

from nobet_scheduler.model import (
    ROLE_COMEZ_BASI,
    ROLE_KAPICI,
    ROLE_NOBET_BASI,
    ROLE_PRIORITY_WEIGHT,
)


def test_role_priority_order_is_comez_basi_then_kapici():
    """Çömez_başı > Kapıcı > Çömez among the roles subject to a flat
    per-assignment reward. nobet_basi is deliberately excluded from
    ROLE_PRIORITY_WEIGHT — a flat reward with no diminishing returns would
    just pile every nobet_basi turn onto the single highest-ranked doctor;
    its distribution is governed instead by the fair-share deviation
    objective (_nobet_basi_fair_shares)."""
    assert ROLE_NOBET_BASI not in ROLE_PRIORITY_WEIGHT
    assert ROLE_PRIORITY_WEIGHT[ROLE_COMEZ_BASI] > ROLE_PRIORITY_WEIGHT[ROLE_KAPICI]
