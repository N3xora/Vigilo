"""`POST /v1/internal/org-plan`: NEXORA Core tells Vigilo the plan an organisation
has, because Core owns the subscription (Stripe checkout and webhook live there).

Not a user-facing route: it is authenticated by an HMAC signature, not a session,
and returns 404 until `NEXORA_SYNC_SECRET` is configured. Idempotent, so Core's
webhook can be redelivered safely.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException, Request

from vigilo_api.core_sync import verify
from vigilo_api.deps import SessionDep
from vigilo_core.config import config
from vigilo_identity.repository import set_org_account_plan
from vigilo_security.audit import AuditEvent, audit

router = APIRouter(prefix="/v1/internal", tags=["internal"])

_ORG_ID = re.compile(r"^org_[A-Za-z0-9]{10,64}$")
_PLANS = {"free", "pro"}
_MAX_BODY = 1024


@router.post("/org-plan")
async def apply_org_plan(request: Request, session: SessionDep) -> dict[str, str]:
    secret = config().nexora_sync_secret
    if not secret:
        raise HTTPException(status_code=404, detail="not found")

    body = await request.body()
    if len(body) > _MAX_BODY or not verify(
        secret,
        request.headers.get("X-Nexora-Timestamp"),
        request.headers.get("X-Nexora-Signature"),
        body,
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body)
        org_id, plan_id = payload["clerk_org_id"], payload["plan_id"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="invalid payload") from None
    if not isinstance(org_id, str) or not _ORG_ID.match(org_id) or plan_id not in _PLANS:
        raise HTTPException(status_code=400, detail="invalid payload")

    account = await set_org_account_plan(session, org_id, plan_id)
    if account is None:
        return {"status": "ignored"}

    await audit(
        session,
        AuditEvent(
            actor="nexora-core",
            action="org_plan_synced",
            subject=org_id,
            account_id=account.id,
            metadata={"plan_id": plan_id},
        ),
    )
    return {"status": "applied"}
