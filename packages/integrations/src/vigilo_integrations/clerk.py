"""Clerk's Backend API, for the one call the product needs it for: removing a
user's sign-in identity when they delete their account. Without it the person
could sign in again and be given a fresh, empty account. No SDK; `transport`
is the same `httpx.MockTransport` seam the other adapters use.
"""

from __future__ import annotations

import httpx

from vigilo_core.config import config
from vigilo_integrations.errors import IdentityProviderError

_USERS_URL = "https://api.clerk.com/v1/users"
_REQUEST_TIMEOUT = 10.0


async def delete_clerk_user(
    clerk_user_id: str, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Idempotent: a user Clerk no longer has (404) counts as deleted."""
    cfg = config()
    if not cfg.clerk_secret_key:
        raise IdentityProviderError("Clerk is not configured (missing secret key)")
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
            response = await client.delete(
                f"{_USERS_URL}/{clerk_user_id}",
                headers={"Authorization": f"Bearer {cfg.clerk_secret_key}"},
            )
    except httpx.HTTPError as exc:
        raise IdentityProviderError("Clerk request failed") from exc
    if response.status_code == 404:
        return
    if response.status_code >= 400:
        raise IdentityProviderError(
            "Clerk rejected the user deletion", status_code=response.status_code
        )
