"""The static plan table: Free and a single paid Pro plan.

Pro is the union of every capability the product has — a single paid
plan that withheld one would leave that feature reachable by no customer.
`repo_connectors_limit` is set but not read by any enforcement code (the
repository connector is deferred, docs/build-roadmap.md's Phase 9 entry).
`monitors_limit` mirrors `targets_limit` — one monitor per target is the
natural ceiling, and monitored scans don't consume `scans_per_month_limit`
(docs/build-roadmap.md's Phase 8 entry). Every plan sets `api_keys_limit`
explicitly, including Free's `0` — the dataclass default would otherwise
mean "unlimited".

Accounts still carrying a retired plan id (`builder`/`studio`/`business`)
resolve to Free via `entitlements()`'s fail-closed fallback.
"""

from __future__ import annotations

from vigilo_billing.models import Plan, PlanId

PLANS: dict[PlanId, Plan] = {
    PlanId.FREE: Plan(
        plan_id=PlanId.FREE,
        targets_limit=1,
        scans_per_month_limit=3,
        active_tier_allowed=False,
        share_links_allowed=False,
        monitors_limit=0,
        api_keys_limit=0,
    ),
    PlanId.PRO: Plan(
        plan_id=PlanId.PRO,
        targets_limit=25,
        scans_per_month_limit=None,
        active_tier_allowed=True,
        share_links_allowed=True,
        monitoring_frequency="daily+custom",
        monitors_limit=25,
        api_keys_limit=25,
        api_rate_limit_per_minute=300,
        white_label_allowed=True,
        repo_connectors_limit=10,
        price_cents=2900,
        currency="usd",
    ),
}
