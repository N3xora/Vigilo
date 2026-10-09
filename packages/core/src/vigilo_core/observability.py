"""Error tracking that stays off until it is configured.

`init_error_tracking()` does nothing unless `SENTRY_DSN` is set, so a fresh
checkout, a CI run and a self-hoster who does not want it behave exactly as
before. When it is on, it is set up to send as little as possible: no personal
data by default, no request bodies, headers, cookies or query strings (they can
carry tokens, emails and invitation links), and no local variables from stack
frames. `sentry_sdk` is imported lazily, so a deployment without the package
still starts.
"""

from __future__ import annotations

import os
import re
from typing import Any

_SCRUBBED_REQUEST_FIELDS = ("data", "headers", "cookies", "query_string", "env")


# Paths that carry a one-time secret in the URL itself.
_SECRET_PATHS = re.compile(r"(/(?:invites|share|invite)/)[^/?#]+")


def scrub_event(event: dict[str, Any], hint: Any = None) -> dict[str, Any]:
    """`before_send` hook: drop everything about the request that could hold a secret."""
    request = event.get("request")
    if isinstance(request, dict):
        for field in _SCRUBBED_REQUEST_FIELDS:
            request.pop(field, None)
        if isinstance(request.get("url"), str):
            request["url"] = _SECRET_PATHS.sub(r"\1[redacted]", request["url"])
    event.pop("user", None)
    return event


def init_error_tracking(service: str) -> bool:
    """Returns whether error tracking was started. `service` names the process
    ("api", "scanner") so events can be told apart."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT") or os.environ.get("ENV", "production"),
        release=os.environ.get("SENTRY_RELEASE") or None,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,  # errors only: no performance tracing, no extra traffic
        before_send=scrub_event,
        server_name=service,
    )
    sentry_sdk.set_tag("service", service)
    return True
