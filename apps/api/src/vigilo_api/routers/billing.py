"""`POST /v1/billing/checkout` + `POST /v1/billing/webhook` (Phase 7).

The webhook route is deliberately public — Stripe authenticates itself via
`verify_webhook_signature()`, not a bearer token, so this reads the raw
request body directly rather than taking a parsed Pydantic model (signature
verification needs the exact bytes Stripe signed). An unrecognized event,
another NEXORA product's subscription on the shared Stripe account, or an
account that doesn't exist yet all return `200`/no-op rather than an error
— a non-2xx makes Stripe retry for days and eventually disable the
endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from vigilo_api.deps import AccountDep, SessionDep
from vigilo_api.schemas import CheckoutRequest, CheckoutResponse, PlanResponse
from vigilo_billing import PLANS, UnrecognizedWebhookEvent, interpret_webhook_event
from vigilo_core.config import config
from vigilo_identity.repository import get_account_by_email, upsert_subscription
from vigilo_integrations.billing import (
    create_checkout_url,
    parse_webhook_event,
    price_to_plan,
    verify_webhook_signature,
)
from vigilo_security.audit import AuditEvent, audit

router = APIRouter(prefix="/v1/billing", tags=["billing"])

# A separate router (bare /v1 prefix, not /v1/billing) for GET /v1/plans —
# the dashboard's billing/upgrade page's plan-comparison data. Genuinely
# public: no account, no session, just the static in-memory PLANS dict.
plans_router = APIRouter(prefix="/v1", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest, account: AccountDep) -> CheckoutResponse:
    billing_page = f"{config().web_app_url or ''}/dashboard/billing"
    checkout_url = await create_checkout_url(
        body.plan_id,
        account.email,
        str(account.id),
        success_url=f"{billing_page}?checkout=success",
        cancel_url=billing_page,
    )
    return CheckoutResponse(checkout_url=checkout_url)


@plans_router.get("/plans", response_model=list[PlanResponse])
async def list_plans() -> list[PlanResponse]:
    return [PlanResponse.model_validate(plan) for plan in PLANS.values()]


@router.post("/webhook")
async def receive_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    raw_body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    payload = parse_webhook_event(raw_body)

    try:
        event = interpret_webhook_event(payload, price_to_plan())
    except UnrecognizedWebhookEvent:
        return {"status": "ignored"}

    account = await get_account_by_email(session, event.account_email)
    if account is None:
        return {"status": "ignored"}

    await upsert_subscription(
        session,
        account_id=account.id,
        plan_id=event.plan_id,
        status=event.status,
        provider=event.provider,
        provider_subscription_id=event.provider_subscription_id,
        current_period_end=event.period_end,
    )
    await audit(
        session,
        AuditEvent(
            actor="stripe",
            action="subscription_updated",
            subject=event.provider_subscription_id,
            account_id=account.id,
            metadata={"plan_id": event.plan_id, "status": event.status},
        ),
    )

    return {"status": "applied"}
