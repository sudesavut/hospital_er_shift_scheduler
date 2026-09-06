"""Tests for role-priority weighting in model.py."""

from nobet_scheduler.model import (
    ROLE_COMEZ_BASI,
    ROLE_KAPICI,
    ROLE_NOBET_BASI,
    ROLE_PRIORITY_WEIGHT,
)


def test_role_priority_order_is_nobet_basi_then_comez_basi_then_kapici():
    """Nöbet_başı > Çömez_başı > Kapıcı > Çömez (Çömez has no weight entry —
    it's excluded from ROLE_PRIORITY_WEIGHT, discouraged/rewarded separately
    via SENIOR_IN_COMEZ_PENALTY instead)."""
    assert (
        ROLE_PRIORITY_WEIGHT[ROLE_NOBET_BASI]
        > ROLE_PRIORITY_WEIGHT[ROLE_COMEZ_BASI]
        > ROLE_PRIORITY_WEIGHT[ROLE_KAPICI]
    )
