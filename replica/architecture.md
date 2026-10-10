# Architecture: Nexora platform shell

Inputs: replica/recon.md, replica/features.csv. Principle: extend the existing Vigilo monorepo; do not rewrite.

## 1. Stack (kept, no change)
| layer | choice | why |
| --- | --- | --- |
| web | Next.js 16 App Router + TS + Tailwind (apps/web) | already built; tokens come from replica-design |
| API | FastAPI async (apps/api) | already built, 388+ tests |
| DB | Postgres + SQLAlchemy 2 + Alembic | one database; migration 0009 adds orgs |
| auth + orgs | Clerk, with Clerk Organizations for invites/roles | already wired; org flows are solved |
| payments | Stripe Checkout + Billing + portal | already built (monthly + yearly Pro) |
| email | Postmark | already integrated |
| jobs | ARQ + Redis (apps/scanner) | already built |
| files | MinIO/S3 | already built |
| hosting | Docker Compose + Caddy on a VPS (docker-compose.self-host.yml) | already built; deploy.sh exists |
No microservices. Other products (Sentinel, CSPM, Gateway) become new routers + packages in this monorepo.

## 2. Tenancy decision
- Organization is the tenant. Every user-owned row carries `org_id`. Account stays the human identity.
- Clerk Organizations is the source of truth for membership and roles; `organizations`/`memberships` mirror it via the existing Clerk webhook path (user.created, organization.*, organizationMembership.*).
- Every existing account gets a personal org (`is_personal`) in the 0009 backfill, so nothing breaks for current users.
- Access rule: no RLS (Postgres is reached by the API with one role). One authorisation check per query: `require_org_member(min_role)` dependency resolves `org_id` from the `X-Org-Id` header or Clerk's active org claim, verifies membership, and passes `org_id` into every repository call. Repositories without an `org_id` parameter are a review failure.
- Roles: owner (billing, delete org), admin (members, keys, products), member (use products), viewer (read reports).
- API keys belong to an org, not a person, so they survive offboarding. Scope strings become `product:action` (`vigilo:scan:run`); old scope names are aliased for one release.

## 3. Schema
See `replica/schema.sql`. 8 new objects: organizations, memberships, product_enablements, usage_counters, stripe_events, org_invites, plus column changes on projects, subscriptions, api_keys, branding_profiles, audit_events.
Hard constraints in the database: one owner per org (partial unique index), one active subscription per org per product (partial unique index), unique usage counter per org/product/meter/month, hashed single-use invite tokens, no negative counters.
Money: plan prices stay in the code plan registry; the DB stores Stripe ids and period end, not amounts.

## 4. Entitlements
Replace the single `PLANS` dict with `PRODUCT_PLANS[product_slug][plan_id]`, one registry per product. `entitlements(org, product)` reads the active subscription for that product, falls back to that product's free plan, fails closed. Vigilo keeps Free + Pro. Sentinel/CSPM/Gateway get the 5-tier ladder from the pricing page; NeuraWall is out of scope (stub).
Open decision to confirm before billing work: the live pricing page is the source of truth, and one org with multiple products means multiple Stripe subscriptions on one customer (one Stripe Customer per org).

## 5. API (new routes; existing /v1 routes gain org scoping)
| method path | what | who | input | output | flow |
| --- | --- | --- | --- | --- | --- |
| GET /v1/me | account + orgs + active org + entitlements | signed in | - | AccountResponse (extended) | F02 |
| POST /v1/orgs | create org | signed in | name, slug | Org | F02 |
| GET /v1/orgs | list my orgs | signed in | - | [Org] | F02 |
| PATCH /v1/orgs/{id} | rename | admin | name | Org | F05 |
| DELETE /v1/orgs/{id} | delete, 30-day soft delete | owner | confirm slug | 202 | - |
| GET /v1/orgs/{id}/members | list | member | - | [Member] | F05 |
| POST /v1/orgs/{id}/invites | invite | admin | email, role | Invite (token once) | F05 |
| POST /v1/invites/{token}/accept | join | signed in | - | Membership | F05 |
| PATCH/DELETE /v1/orgs/{id}/members/{aid} | change role / remove | admin | role | Member | F05 |
| GET /v1/orgs/{id}/products | launcher data: status, plan, usage | member | - | [ProductCard] | F02, F03 |
| POST /v1/orgs/{id}/products/{slug}/enable | enable | admin | - | ProductCard | F03 |
| GET /v1/orgs/{id}/usage | meters per product | member | period | [Usage] | F04 |
| POST /v1/billing/checkout | now takes product_slug, plan_id, interval | owner/admin | body | url | F04 |
| POST /v1/billing/portal | org's Stripe customer | owner/admin | - | url | F04 |
| GET /v1/plans?product= | plans per product | public | - | [Plan] | F04 |
| GET /v1/orgs/{id}/audit | audit trail | admin | cursor | [Event] | - |
| /v1/orgs/{id}/api-keys | existing key routes under org | admin | body | key | F06 |
| /public/v1/{product}/... | key-authenticated; Vigilo's existing routes stay as aliases | key | - | - | F06 |
Stub products: `POST /v1/sentinel/analyze`, `/v1/cspm/audit`, `/v1/gateway/...` return 501 until built; each is metered through `usage_counters` from day one.
Webhooks in: Stripe (checkout.session.completed, customer.subscription.*, invoice.payment_failed) with `stripe_events` dedupe; Clerk (user, organization, membership). Webhooks out: none yet.
Jobs: nightly usage rollover check, expired-invite cleanup (daily), 30-day org hard-delete sweep, existing monitor cron unchanged.

## 6. Parts that bite
- Migration safety: backfill personal orgs in one transaction per table batch, three-step deploy (add nullable -> backfill + dual-write -> set not null). Never in one release.
- Idempotency: Stripe events deduped by `stripe_events.event_id`; subscription upsert keyed on `provider_subscription_id` (already so).
- Race: two admins enabling or subscribing at once, covered by the partial unique indexes; counters use `on conflict do update`.
- Time: usage periods are UTC months; show the reset date in UTC.
- Rate limits: per-key limit already exists; add per-org ceiling.
- Multi-tenancy leaks: a cross-org test per router (user in org A requests org B's resource -> 404, not 403).
- GDPR: deleting an account removes memberships; deleting an org cascades after the 30-day window; `audit_events.org_id` is set null, not deleted (append-only).
- Clerk lag: webhook ordering is not guaranteed; membership upsert is idempotent and the API lazily provisions on first request, as /v1/me already does.
- Scan egress safety remains the Vigilo invariant; new products must not import probes in the control plane.

## 7. Build order
1. Vertical slice: sign up -> personal org -> launcher (S21) showing Vigilo -> existing scan in that org -> report. Tables: organizations, memberships, product_enablements; org-scoped projects. Routes: /v1/me, /v1/orgs, /v1/orgs/{id}/products. Screens S20, S21 (S10-S17 re-parented under org).
2. Must-haves: org switcher + create (S20), members + roles + invites (S22), unified billing (S23), usage + quotas (S25), marketing home/products/pricing (S01-S04), per-product subscriptions.
3. Should-haves: org-wide API keys and scopes (S24), audit UI (S26), 5-tier plans for Sentinel/CSPM/Gateway, trust page, dev docs.
4. Could-haves: product stubs with pasted input (S27), bundles.
5. Fixes from replica-entrepreneur after it runs.

## 8. Not doing
NeuraWall engine, Marketplace/Labs, enterprise contracts, microservices, rewrite of Vigilo.
