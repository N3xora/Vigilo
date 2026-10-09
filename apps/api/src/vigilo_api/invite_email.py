"""Emailing an organisation invitation.

The link in the email is the same one the inviter is shown in the web app; the
email is a convenience, never the only way to deliver it. So sending is
best-effort: any failure is reported to the caller as a status and the invite
still exists.

Because the email goes out from our own sender on behalf of a user, it is
limited so it cannot be used to mail strangers in bulk: per organisation, per
inviter and per recipient address. The text is fixed apart from the
organisation name and inviter address, which are escaped, flattened to one
line and truncated, and the inviter's address is always shown so the reader can
see who is asking.
"""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from typing import Literal

from vigilo_core.config import config
from vigilo_integrations.errors import MailDeliveryFailed
from vigilo_integrations.mail import send_transactional_email
from vigilo_security.rate_limit import check_rate, get_redis_client

EmailStatus = Literal["sent", "not_configured", "rate_limited", "failed"]

# (limit, window in seconds). Tuned so a team inviting colleagues is never
# blocked, while bulk misuse stops quickly.
PER_ORG = (20, 3600)
PER_INVITER = (20, 3600)
PER_RECIPIENT = (3, 86400)

# Replaced in tests with a function bound to an httpx.MockTransport.
deliver = send_transactional_email


def _one_line(value: str, limit: int) -> str:
    flat = re.sub(r"\s+", " ", value).strip()
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def render_invite_email(
    *, org_name: str, inviter_email: str, role: str, link: str, expires_at: datetime
) -> tuple[str, str, str]:
    """Returns `(subject, html_body, text_body)`."""
    brand = config().brand.brand.name
    org = _one_line(org_name, 60)
    inviter = _one_line(inviter_email, 120)
    expires = expires_at.strftime("%d %B %Y")

    subject = f"You're invited to join {org} on {brand}"
    text = (
        f'{inviter} invited you to join "{org}" on {brand} as {role}.\n\n'
        f"Accept the invitation: {link}\n\n"
        f"The link works once, only for this email address, and expires on {expires} (UTC). "
        "Nothing happens unless you accept.\n\n"
        "If you were not expecting this, you can ignore the email."
    )
    esc = html.escape
    body = (
        f"<p>{esc(inviter)} invited you to join <strong>&ldquo;{esc(org)}&rdquo;</strong> "
        f"on {esc(brand)} as {esc(role)}.</p>"
        f'<p><a href="{esc(link, quote=True)}">Accept the invitation</a></p>'
        f"<p>The link works once, only for this email address, and expires on {esc(expires)} "
        "(UTC). Nothing happens unless you accept.</p>"
        "<p>If you were not expecting this, you can ignore the email.</p>"
    )
    return subject, body, text


def invite_link(token: str) -> str | None:
    base = config().web_app_url
    return f"{base.rstrip('/')}/invite/{token}" if base else None


def _configured() -> bool:
    cfg = config()
    return bool(cfg.postmark_server_token and cfg.mail_from_address and cfg.web_app_url)


async def send_invite_email(
    *,
    org_id: str,
    org_name: str,
    inviter_id: str,
    inviter_email: str,
    to: str,
    role: str,
    token: str,
    expires_at: datetime,
) -> EmailStatus:
    if not _configured():
        return "not_configured"
    link = invite_link(token)
    assert link is not None  # _configured() checked web_app_url

    try:
        redis = get_redis_client()
        recipient = hashlib.sha256(to.lower().encode()).hexdigest()[:32]
        for key, (limit, window) in (
            (f"invite-email:org:{org_id}", PER_ORG),
            (f"invite-email:inviter:{inviter_id}", PER_INVITER),
            (f"invite-email:to:{recipient}", PER_RECIPIENT),
        ):
            if not (await check_rate(redis, key, limit, window)).allowed:
                return "rate_limited"
    except Exception:  # noqa: BLE001 - never email when the limiter cannot be consulted
        return "failed"

    subject, html_body, text_body = render_invite_email(
        org_name=org_name,
        inviter_email=inviter_email,
        role=role,
        link=link,
        expires_at=expires_at,
    )
    try:
        await deliver(to=to, subject=subject, html_body=html_body, text_body=text_body)
    except MailDeliveryFailed:
        return "failed"
    return "sent"
