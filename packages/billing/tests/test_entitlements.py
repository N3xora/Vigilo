from __future__ import annotations

from vigilo_billing.entitlements import entitlements
from vigilo_billing.models import PlanId


def test_free_plan_entitlements():
    result = entitlements("free")
    assert result.plan_id == PlanId.FREE
    assert result.targets_limit == 1
    assert result.scans_per_month_limit == 3
    assert result.active_tier_allowed is False
    assert result.share_links_allowed is False
    assert result.monitoring_frequency is None
    assert result.monitors_limit == 0
    assert result.api_keys_limit == 0
    assert result.white_label_allowed is False


def test_pro_plan_includes_every_capability():
    result = entitlements("pro")
    assert result.plan_id == PlanId.PRO
    assert result.targets_limit == 25
    assert result.scans_per_month_limit is None
    assert result.active_tier_allowed is True
    assert result.share_links_allowed is True
    assert result.monitoring_frequency == "daily+custom"
    assert result.monitors_limit == 25
    assert result.api_keys_limit == 25
    assert result.api_rate_limit_per_minute == 300
    assert result.white_label_allowed is True
    assert (result.price_cents, result.currency) == (2900, "usd")


def test_free_plan_has_no_price():
    assert entitlements("free").price_cents == 0


def test_retired_plan_ids_fall_back_to_free():
    """builder/studio/business were collapsed into Pro; an account still
    carrying one must fail closed, not keep paid access."""
    for retired in ("builder", "studio", "business"):
        assert entitlements(retired).plan_id == PlanId.FREE


def test_none_plan_id_defaults_to_free():
    assert entitlements(None).plan_id == PlanId.FREE


def test_unrecognized_plan_id_defaults_to_free():
    """Fail closed: an unrecognized plan_id (a typo, a stale/removed plan)
    must never fail open into an unrestricted plan."""
    assert entitlements("not-a-real-plan").plan_id == PlanId.FREE
