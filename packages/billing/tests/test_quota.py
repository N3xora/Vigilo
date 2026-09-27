from __future__ import annotations

from vigilo_billing.entitlements import entitlements
from vigilo_billing.models import Meter
from vigilo_billing.quota import consume


def test_consume_allows_when_under_the_limit():
    free = entitlements("free")
    decision = consume(current_usage=0, amount=1, meter=Meter.TARGETS, entitlements=free)
    assert decision.allowed is True
    assert decision.limit == 1


def test_consume_allows_exactly_at_the_limit():
    free = entitlements("free")
    decision = consume(current_usage=0, amount=1, meter=Meter.TARGETS, entitlements=free)
    assert decision.allowed is True


def test_consume_denies_one_over_the_limit():
    free = entitlements("free")  # targets_limit = 1
    decision = consume(current_usage=1, amount=1, meter=Meter.TARGETS, entitlements=free)
    assert decision.allowed is False
    assert decision.current == 1
    assert decision.limit == 1


def test_consume_denies_when_amount_would_push_over_the_limit():
    pro = entitlements("pro")  # targets_limit = 25
    decision = consume(current_usage=24, amount=2, meter=Meter.TARGETS, entitlements=pro)
    assert decision.allowed is False


def test_consume_is_unlimited_for_a_none_limit():
    pro = entitlements("pro")  # scans_per_month_limit = None
    decision = consume(
        current_usage=100_000, amount=1, meter=Meter.SCANS_MONTHLY, entitlements=pro
    )
    assert decision.allowed is True
    assert decision.limit is None
    assert decision.reason == "unlimited"


def test_consume_checks_the_scans_monthly_meter_independently_of_targets():
    free = entitlements("free")  # scans_per_month_limit = 3
    decision = consume(current_usage=3, amount=1, meter=Meter.SCANS_MONTHLY, entitlements=free)
    assert decision.allowed is False


def test_consume_denies_any_monitor_on_the_free_plan():
    free = entitlements("free")  # monitors_limit = 0
    decision = consume(current_usage=0, amount=1, meter=Meter.MONITORS, entitlements=free)
    assert decision.allowed is False
    assert decision.limit == 0


def test_consume_allows_monitors_up_to_the_pro_limit():
    pro = entitlements("pro")  # monitors_limit = 25
    decision = consume(current_usage=24, amount=1, meter=Meter.MONITORS, entitlements=pro)
    assert decision.allowed is True


def test_consume_denies_any_api_key_on_the_free_plan():
    free = entitlements("free")  # api_keys_limit = 0
    decision = consume(current_usage=0, amount=1, meter=Meter.API_KEYS, entitlements=free)
    assert decision.allowed is False
    assert decision.limit == 0


def test_consume_allows_api_keys_up_to_the_pro_limit():
    pro = entitlements("pro")  # api_keys_limit = 25
    decision = consume(current_usage=24, amount=1, meter=Meter.API_KEYS, entitlements=pro)
    assert decision.allowed is True
