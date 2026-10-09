"""API-key verification for the public REST API (`/public/v1/*`,
Phase 9) — a parallel, distinct auth scheme from `auth.py`'s Clerk JWT
verification, per the vision doc's "key-authenticated surface distinct
from the session-authenticated one." Mirrors `auth.py`'s shape: a small,
pure verification function plus the FastAPI dependency that calls it.

Unlike Clerk verification, there is no external JWKS call — a key is
"verified" by hashing the presented plaintext and looking up the hash, so
this needs a session, not a signing-key resolver.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from vigilo_api.deps import SessionDep, _bearer_token
from vigilo_billing import entitlements
from vigilo_identity.models import Account
from vigilo_identity.org_repository import plan_id_for_org
from vigilo_identity.repository import (
    get_account_by_id,
    get_api_key_by_hash,
    hash_api_key,
    mark_api_key_used,
)
from vigilo_security.rate_limit import check_rate, get_redis_client

PRODUCT = "vigilo"
_ACTIONS = (
    "scan:run",
    "scan:read",
    "project:read",
    "report:read",
    "monitor:read",
    "monitor:write",
)
# Scopes are `product:resource:action`. Keys issued before products existed
# carry the bare `resource:action` form; those keep working as Vigilo scopes.
ALL_SCOPES = frozenset(f"{PRODUCT}:{a}" for a in _ACTIONS)


def normalize_scope(scope: str) -> str:
    """The product-qualified form of a scope (bare legacy scopes are Vigilo's)."""
    return f"{PRODUCT}:{scope}" if scope in _ACTIONS else scope


def normalize_scopes(scopes: Iterable[str]) -> list[str]:
    return sorted({normalize_scope(s) for s in scopes})


class KeyAccount(Account):
    """The account behind an API key, plus the organisation the key belongs to."""

    org_id: uuid.UUID


async def require_api_key(
    request: Request, session: SessionDep
) -> tuple[KeyAccount, frozenset[str]]:
    raw_key = _bearer_token(request)
    api_key = await get_api_key_by_hash(session, hash_api_key(raw_key))

    if api_key is None or api_key.revoked_at is not None:
        raise HTTPException(status_code=401, detail="invalid or revoked API key")

    account = await get_account_by_id(session, api_key.account_id)
    if account is None:
        raise HTTPException(status_code=401, detail="invalid or revoked API key")

    await mark_api_key_used(session, api_key.id, datetime.now(UTC))
    await session.commit()  # the usage stamp must survive even if the handler later fails

    # The key acts in its organisation, not its creator's personal one.
    key_account = KeyAccount(**account.model_dump(), org_id=api_key.org_id)
    return key_account, frozenset(normalize_scopes(api_key.scopes))


ApiKeyAuthDep = Annotated[tuple[KeyAccount, frozenset[str]], Depends(require_api_key)]


def require_scope(scope: str) -> Depends:
    """A dependency factory used in the *annotation*, not as a default
    value — `account: Annotated[Account, require_scope("scan:run")]` in
    each public-API route — matching this codebase's existing
    `Annotated[X, Depends(...)]` convention (`deps.py`'s `AccountDep`
    etc.) rather than FastAPI's older `= Depends(...)` default-argument
    style, which ruff's B008 rightly flags as fragile in general (even
    though FastAPI special-cases it) since Python only evaluates a
    default expression once at function-definition time.

    Also enforces the plan's per-minute rate limit (vision §12: "Rate
    limits per plan; 429 with Retry-After") — keyed by the key's *organisation*,
    not by the individual API key: "per plan" reads as one shared budget for
    the organisation, not a separate budget per key it happens to have issued."""

    async def _check(auth: ApiKeyAuthDep, session: SessionDep) -> KeyAccount:
        account, scopes = auth
        needed = normalize_scope(scope)
        if needed not in scopes:
            raise HTTPException(
                status_code=403, detail=f"API key is missing the required scope: {needed}"
            )

        # The budget belongs to the key's organisation and its plan.
        limit = entitlements(
            await plan_id_for_org(session, account.org_id)
        ).api_rate_limit_per_minute
        decision = await check_rate(get_redis_client(), f"ratelimit:{account.org_id}", limit)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

        return account

    return Depends(_check)
