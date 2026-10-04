"""Clerk session-JWT verification (ADR-0003 Phase 3 addendum: Clerk chosen
over Supabase Auth). Stateless, JWKS-based — no Clerk SDK dependency.

`get_signing_key` is the same dependency-injection seam used throughout the
codebase (`egress_guard.Resolver`, `ownership.TxtResolver`): the default
fetches Clerk's real JWKS over the network; tests inject a fake key so
verification logic (signature, expiry, claim extraction) is tested with a
locally-generated keypair, never a live Clerk instance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from vigilo_core.config import config
from vigilo_core.errors import ErrorCode, StructuredError

GetSigningKey = Callable[[str], Any]


@dataclass(frozen=True)
class ClerkClaims:
    user_id: str
    email: str | None
    # Set when the session is acting inside a Clerk organisation. The
    # `vigilo-api` JWT template must include `org_id` (`{{org.id}}`) and
    # `org_role` (`{{org.role}}`); without them every request resolves to the
    # caller's personal account exactly as before.
    org_id: str | None = None
    org_role: str | None = None


class ClerkAuthError(StructuredError):
    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, **context)


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    cfg = config()
    if not cfg.clerk_jwks_url:
        raise StructuredError(ErrorCode.CONFIGURATION_ERROR, "CLERK_JWKS_URL is not set")
    return PyJWKClient(cfg.clerk_jwks_url)


def _default_get_signing_key(token: str) -> Any:
    return _jwk_client().get_signing_key_from_jwt(token).key


def verify_clerk_jwt(token: str, get_signing_key: GetSigningKey | None = None) -> ClerkClaims:
    resolve = get_signing_key or _default_get_signing_key

    try:
        signing_key = resolve(token)
        payload = jwt.decode(
            token, signing_key, algorithms=["RS256"], options={"verify_aud": False}
        )
    except jwt.PyJWTError as exc:
        raise ClerkAuthError("invalid or expired session token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise ClerkAuthError("session token is missing a subject claim")

    # Clerk's default session token nests the organisation under `o`
    # (`o.id`, `o.rol`); a custom JWT template uses flat claims.
    nested = payload.get("o") if isinstance(payload.get("o"), dict) else {}
    org_id = payload.get("org_id") or nested.get("id") or None
    org_role = payload.get("org_role") or nested.get("rol") or None
    if org_role and not str(org_role).startswith("org:"):
        org_role = f"org:{org_role}"
    return ClerkClaims(
        user_id=user_id,
        email=payload.get("email"),
        org_id=str(org_id) if org_id else None,
        org_role=str(org_role) if org_role else None,
    )
