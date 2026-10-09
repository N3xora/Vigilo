"""interpret_webhook_event(): turns a verified Stripe event (the dict
`vigilo_integrations.billing.parse_webhook_event()` hands back) into
billing's own `MoREvent`. Pure — no session, no I/O, no config: the caller
passes the Stripe-price → plan mapping in.

Vigilo shares its Stripe account with the rest of the NEXORA platform, so
every subscription event on that account arrives here. Only subscriptions
carrying `metadata.vigilo_account_email` (set by Vigilo's own checkout,
`create_checkout_url()`) on a Vigilo price are applied — anything else is
another product's subscription and is ignored, never an error.
`metadata.vigilo_org_id` names the organisation that pays; without it
(subscriptions made before organisations) the paying account's personal
organisation is used.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from vigilo_billing.errors import UnrecognizedWebhookEvent
from vigilo_billing.models import MoREvent

_RECOGNIZED_EVENT_TYPES = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)

# Stripe keeps retrying a failed renewal while `past_due`, then cancels —
# access continues through that window rather than dropping on the first
# declined card. Every other status (canceled, unpaid, incomplete,
# incomplete_expired, paused) means no paid access.
_ACTIVE_STRIPE_STATUSES = frozenset({"active", "trialing", "past_due"})


def interpret_webhook_event(payload: dict[str, Any], plan_by_price_id: dict[str, str]) -> MoREvent:
    event_type = payload.get("type")
    if event_type not in _RECOGNIZED_EVENT_TYPES:
        raise UnrecognizedWebhookEvent(
            "unrecognized billing webhook event type", event_type=str(event_type)
        )

    try:
        subscription = payload["data"]["object"]
        metadata = subscription.get("metadata") or {}
        account_email = metadata.get("vigilo_account_email")
        item = subscription["items"]["data"][0]
        plan_id = plan_by_price_id.get(item["price"]["id"])
        if not account_email or plan_id is None:
            raise UnrecognizedWebhookEvent("not a Vigilo subscription", event_type=event_type)

        # Newer Stripe API versions moved the period onto the item.
        period_end_raw = item.get("current_period_end") or subscription.get("current_period_end")
        status = (
            "active"
            if event_type != "customer.subscription.deleted"
            and subscription["status"] in _ACTIVE_STRIPE_STATUSES
            else "canceled"
        )
        created_raw = payload.get("created")
        customer = subscription.get("customer")
        recurring = (item.get("price") or {}).get("recurring") or {}
        return MoREvent(
            event_type=event_type,
            provider="stripe",
            provider_subscription_id=subscription["id"],
            account_email=account_email,
            plan_id=plan_id,
            status=status,
            period_end=datetime.fromtimestamp(period_end_raw, UTC) if period_end_raw else None,
            org_id=metadata.get("vigilo_org_id") or None,
            account_id=metadata.get("vigilo_account_id") or None,
            customer_id=customer if isinstance(customer, str) else None,
            event_created=datetime.fromtimestamp(created_raw, UTC) if created_raw else None,
            interval="year" if recurring.get("interval") == "year" else "month",
            cancel_at_period_end=bool(
                subscription.get("cancel_at_period_end") or subscription.get("cancel_at")
            ),
        )
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        # A recognized event type with a malformed/incomplete payload is
        # discarded whole, never partially applied.
        raise UnrecognizedWebhookEvent(
            "malformed billing webhook payload", event_type=event_type
        ) from exc
