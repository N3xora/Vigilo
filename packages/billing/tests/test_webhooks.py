from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from vigilo_billing.errors import UnrecognizedWebhookEvent
from vigilo_billing.webhooks import interpret_webhook_event

_PRICES = {"price_pro": "pro"}
_PERIOD_END = 1_792_022_400  # 2026-10-15T00:00:00Z


def _event(
    event_type: str = "customer.subscription.created",
    status: str = "active",
    price: str = "price_pro",
    metadata: dict | None = None,
    item_period_end: int | None = _PERIOD_END,
) -> dict:
    item: dict = {"price": {"id": price}}
    if item_period_end is not None:
        item["current_period_end"] = item_period_end
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_123",
                "status": status,
                "metadata": {"vigilo_account_email": "owner@example.com"}
                if metadata is None
                else metadata,
                "items": {"data": [item]},
            }
        },
    }


def test_maps_a_vigilo_subscription():
    event = interpret_webhook_event(_event(), _PRICES)
    assert event.provider == "stripe"
    assert event.provider_subscription_id == "sub_123"
    assert event.account_email == "owner@example.com"
    assert event.plan_id == "pro"
    assert event.status == "active"
    assert event.period_end == datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_statuses_that_keep_paid_access(status):
    event = interpret_webhook_event(_event("customer.subscription.updated", status), _PRICES)
    assert event.status == "active"


@pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete", "incomplete_expired"])
def test_statuses_that_end_paid_access(status):
    event = interpret_webhook_event(_event("customer.subscription.updated", status), _PRICES)
    assert event.status == "canceled"


def test_a_deleted_subscription_is_canceled_whatever_its_status_says():
    event = interpret_webhook_event(_event("customer.subscription.deleted", "active"), _PRICES)
    assert event.status == "canceled"


def test_falls_back_to_the_subscription_level_period_end():
    payload = _event(item_period_end=None)
    payload["data"]["object"]["current_period_end"] = _PERIOD_END
    assert interpret_webhook_event(payload, _PRICES).period_end == datetime(
        2026, 10, 15, tzinfo=UTC
    )


def test_tolerates_a_missing_period_end():
    assert interpret_webhook_event(_event(item_period_end=None), _PRICES).period_end is None


def test_ignores_an_unrelated_event_type():
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(_event("invoice.paid"), _PRICES)


def test_ignores_another_products_subscription_on_the_shared_account():
    """NEXORA's own subscriptions share the Stripe account: no Vigilo
    metadata, or a price that isn't Vigilo's, is not ours to apply."""
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(_event(metadata={"orgId": "org_1"}), _PRICES)
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(_event(price="price_nexora"), _PRICES)


def test_ignores_everything_when_no_price_is_configured():
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(_event(), {})


def test_raises_for_a_malformed_recognized_event():
    payload = copy.deepcopy(_event())
    payload["data"]["object"]["items"] = {"data": []}
    with pytest.raises(UnrecognizedWebhookEvent):
        interpret_webhook_event(payload, _PRICES)
