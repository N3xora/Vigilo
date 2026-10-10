# Backend status (2026-10-07)

Scope done: step 1 of the tenancy migration plus the org API. Stack unchanged (FastAPI, SQLAlchemy, Alembic, Clerk, Stripe, Postmark).

## Built
- Migration `0010_organizations`: organizations, memberships (one-owner partial unique index), product_enablements, usage_counters, org_invites; nullable `org_id` on projects, subscriptions, api_keys, branding_profiles; `product_slug` and `billing_interval` on subscriptions; backfills a personal org + owner membership + Vigilo enablement per account. Tested on a database holding existing rows: backfill correct, downgrade/upgrade round-trips, `alembic check` shows no drift.
- `vigilo_identity.org_repository`: create/list orgs, lazy `ensure_personal_org`, members, role changes, invites (sha256 token at rest, shown once, 7-day expiry, bound to invitee email), product enablement, atomic usage counters (upsert-increment).
- API (`routers/orgs.py`, 11 routes) with `require_org_role(min)` guard: non-member -> 404, below role -> 403.
- 8 new tests (`apps/api/tests/test_orgs.py`): cross-org access returns 404 on every route, invite flow and role gates, wrong-email invite rejected, owner immutable, enablement, 10 concurrent usage increments sum to 10.
- Full suite: 668 passed, 5 failed -> 1 fixed (expected-tables test updated), 4 remain: object-storage tests; MinIO image cannot be pulled here (quay.io 401). Not related to this change, not verified green.

## Update: cutover pass (items 1, 2, 4)
- 0011_org_id_not_null: repairs rows written after 0010 (accounts without a personal org, null org_id), then `org_id` NOT NULL on projects, subscriptions, api_keys, branding_profiles. Tested on a populated scratch DB incl. downgrade/upgrade and `alembic check`.
- All four writers stamp the creator's personal org (`personal_org_id()`); tests in `test_org_stamping.py`.
- Vigilo scans are metered into `usage_counters` in the same transaction as the scan job, on `/v1/scans` and `/public/v1/scans`; denied scans are not counted (`test_usage_metering.py`). Quotas still use the old rolling count.
- Web console now calls the real org endpoints; org switcher (cookie preference, membership re-checked), create-org form, enable-product button.
- **Reads are now org-scoped (follow-up pass).** Migration 0012 makes projects and branding one-per-org. Two rules:
  - target-specific routes (target, verification, monitors, scores, alerts, share links, risks, report controls) use the caller's role in the *target's own* org, no header needed; non-members get 404, too-junior members 403;
  - list/create routes (targets, API keys, branding) act in the *active* org: `X-Org-Id`, else the personal org; a header for an org you are not in is 404, a non-UUID is 422.
  Roles: viewer reads; member adds targets, verifies, runs monitors, accepts risks; admin manages API keys, branding, share links, owner-level report controls; owner everything.
  Plan limits (targets, monitors, API keys, share links, white-label, API rate limit) follow the org owner's plan, not the caller's. API keys carry their org and act in it, so they survive their creator leaving. `/v1/orgs` and `GET /v1/targets/{id}` return the org's entitlements; the dashboard uses them.
  Tests: `test_active_org.py` (10 cases incl. cross-org key, quota-follows-owner, removed member, teammate acts first).
- **Per-org billing (follow-up pass, migration 0013).**
  - The subscription belongs to the organisation and a product; the account on the row is who paid. An org's plan = its own active subscription, else free (`plan_id_for_org`). A personal Pro plan no longer carries into other orgs the same person owns; a free owner's team stays free unless the team subscribes.
  - Checkout (`POST /v1/billing/checkout`, owner/admin, active org): puts `vigilo_org_id` in the Stripe subscription metadata, refuses with 409 if the org already has a plan, reuses the org's Stripe customer (`organizations.billing_customer_id`, saved from the first webhook) so an org never has two. Portal: the active org's subscription, owner/admin.
  - Webhook: org from metadata, else (subscriptions made before orgs) the payer's personal org. Out-of-order events are ignored by comparing Stripe's event time with the last one applied (`stale`); replays are idempotent (keyed by subscription id). Unknown org: ignored with 200.
  - Personal-org subscriptions still set the legacy `accounts.plan_id` that `/v1/me` reads; team subscriptions do not.
  - Tests: `test_org_billing.py` (12), Stripe mocked at the HTTP layer. **Nothing was run against real Stripe.**
  - Behaviour change to know: team orgs created before this pass followed their owner's plan; they are now on the free plan until the team subscribes. Existing personal subscriptions were backfilled to personal orgs in 0009 and are unaffected.
- Still account-level or missing: the anonymous email scan path (personal org), monitor alert recipient (the account that created the monitor), `/v1/me` entitlements (personal), Stripe products for Sentinel/CSPM/Gateway/NeuraWall, a cross-product billing page, renewal-reminder emails, `invoice.payment_failed` handling beyond the subscription status.

## Not done (so the matrix says `partial`)
- Step 2 of the migration: existing routers (targets, scans, api-keys, branding, billing) still scope by `account_id`; they do not write `org_id`. Until they do, `org_id` cannot be made NOT NULL (step 3). Rows created after the backfill have `org_id = NULL`.
- Per-product Stripe billing: checkout/portal/webhook still account-level, Vigilo-only. Needs the per-org Stripe customer, `product_slug` on checkout, and `stripe_events` dedupe. Stripe test keys and the user's Stripe account are required; I did not touch Stripe.
- Clerk organization webhooks (organization.*, membership.*): not wired. Memberships live only in our DB for now.
- Usage metering: the counter and endpoint exist; Vigilo scans are not written to it yet (they still use the rolling scan count), so Vigilo shows 0 used.
- Org-wide API keys with `product:action` scopes; audit-log `org_id` and endpoint; org deletion with 30-day soft delete; invite email via Postmark.
- Web console still on the fake data layer; swapping in these endpoints needs the Clerk JWT flow and an active-org selector (`X-Org-Id`).

## Security checklist
- [x] no new secrets; `.env.example` unchanged (no new variables)
- [x] input validated server-side (pydantic, slug regex, role whitelist)
- [x] authorisation on every org route, tested with a second user (404)
- [ ] rate limits on invite creation (sends no email yet; add when Postmark is wired)
- [x] invite tokens hashed at rest
- [ ] webhooks verify signatures (existing Stripe handler does; Clerk org webhooks not built)
- [ ] `npm audit` / dependency audit not run this pass
- [ ] privacy policy processor list: no new processors

## Invite emails (2026-10-08)
- `POST /v1/orgs/{id}/invites` and the new `POST .../invites/{invite_id}/resend` email the invitation through Postmark and return `email_status`: `sent`, `not_configured` (token, from address or `WEB_APP_URL` missing), `rate_limited`, or `failed`. The invite and its one-time link exist in every case; the UI shows the link and says what happened to the email.
- Resend rotates the token (the old link stops working) and extends the expiry to 7 days.
- Limits (Redis, fixed window): 20 per organisation per hour, 20 per inviter per hour, 3 per recipient address per day. If the limiter cannot be reached, nothing is emailed (fail closed).
- Content: fixed text plus organisation name and inviter address, which are HTML-escaped, collapsed to one line and truncated (subject cannot carry newlines or markup). The inviter's address is always shown to the recipient.
- Committed before sending so the link is live when the email arrives. Mail is sent from `MAIL_FROM_ADDRESS`, which `.env.example` sets to `scans@vigilo.io`: use a sender that suits invitations (and confirm you own that domain) before enabling.
- Privacy page: added a short "People invited to an organisation" section and named invitations in the email-provider line. Have it reviewed; it is a factual description, not legal advice.
- Tests: `test_invite_email.py` (9), Postmark mocked at the HTTP layer; real Redis. **No real email was sent.**
- Not done: bounce/complaint handling, an unsubscribe-style "block invites from this organisation", per-IP limits.

## Cross-product billing summary (2026-10-08, migration 0014)
- `GET /v1/billing/summary` (owner/admin, active org): one line per product (Vigilo, Sentinel, CSPM, Gateway, NeuraWall) with plan, `active` or `free`, cadence, display price, next date, `cancel_at_period_end`, and whether it can be bought here; plus totals per cadence (monthly and yearly are shown separately, never converted).
- Pending cancellations are now captured from Stripe's `cancel_at_period_end` (or `cancel_at`) and cleared by a later event that unsets it (`subscriptions.cancel_at_period_end`), so the page says "Ends <date>" instead of "Renews".
- Prices are the plan registry's display prices, not Stripe's; invoices from Stripe remain the record. Taxes are not included and the page says so.
- Only Vigilo has a plan registry and Stripe prices; the other four always show Free and "Not available to buy yet", so the table will not show a charge that cannot exist.
- Tests: 6 added to `test_org_billing.py` (free baseline, plan and totals, cadences kept apart, cancellation shown then cleared, cancelled back to free, role and per-org isolation). Stripe mocked; nothing run against real Stripe.
- Not done: invoice list and payment method (the portal covers them), tax, proration previews, usage-based charges, a cross-org view for people in several orgs.

## Audit log (2026-10-08, migration 0015)
- `audit_events.org_id` (indexed with `occurred_at`). **Not a foreign key**, because the table is append-only (a trigger rejects UPDATE/DELETE) and an ON DELETE rule would be exactly that; verified on a populated table that the trigger still blocks updates after the migration. Rows written before 0015 keep a null org (they cannot be updated); the read side shows them in the acting account's personal organisation only.
- Recorded now, with the org: org created; invite created/resent/withdrawn/accepted; role changed; member removed/left; product enabled; API key created/revoked (prefix and name, never the key); branding updated (field names only); target added; monitor enabled/disabled; share link created/revoked; checkout started; billing portal opened; and the existing events (suppressions, scans, quota, ownership verified, subscription updated, scheduled scans) now carry their org.
- `GET /v1/orgs/{id}/audit` (owner/admin; non-members 404): newest first, keyset cursor (no skipped or repeated rows while new events arrive), optional `action` filter (validated), `limit` 1-100, plus the distinct actions for a filter menu. People are shown by email, automatic actors as Stripe/Scanner/Monitoring/API; a removed account reads "Former member". Metadata keys that look like secrets are dropped on read as a second line of defence.
- UI `/console/audit`: plain GET filter form, table with UTC times, one sentence per action (`lib/nexora/audit-labels.ts`, unknown actions fall back to their name), "Older events" link.
- Tests: `test_audit_log.py` (8): actions and details recorded, secrets/tokens absent, admin-only and 404 for outsiders, per-org isolation, pagination and filter, legacy events, system actors.
- Not done: export, retention policy, a way for the owner to see failed sign-ins (Clerk holds those), events for actions that still write nothing (scan submissions through the API record only authorisation/denial, API-key use is not logged), per-event detail view.

## Pre-deploy fixes (2026-10-09, migration 0017)
- **Account deletion.** `GET /v1/me/deletion-check` and `POST /v1/me/delete` (type your own email). Blocked, with the reason, while an organisation you own still has other members or a paid plan that is still renewing (a plan set to end is fine). Deletes, in one transaction: the account, every organisation you own with all its targets, scans, findings, reports, share links, monitors, alerts, risks, keys, branding, plans, usage, invitations and memberships; your memberships elsewhere. Things you created in someone else's organisation are handed to that organisation's owner as "created by". After the commit: stored evidence and report files are removed and the Clerk user is deleted, both best-effort and reported (`storage_cleanup`, `identity_removed`); a failure there never undoes the deletion.
- **What stays**, stated on the account page, in the privacy policy and `docs/self-hosting.md`: the append-only audit log (pseudonymous id, shown as "Former member"; the deletion itself is logged without an address), other organisations' data, Stripe customers and invoices.
- Migration 0017 drops the foreign key from `audit_events.account_id` so the trail can outlive the account. Verified on a populated table: the account deletes, the event stays, the append-only trigger still blocks updates. Downgrade refuses once such orphaned events exist, by design.
- Tests: `test_account_deletion.py` (10): full removal, audit survival, email confirmation, member and plan blockers, kept team data, isolation between people, outside failures not undoing the deletion, the Clerk call.
- **Ownership transfer does not exist**, so an owner with a team must remove every other member before deleting their account. Add transfer before real teams use this.
- **Error tracking**: `vigilo_core.observability.init_error_tracking()` in the API and scanner, off unless `SENTRY_DSN` is set (`.env.example`, compose pass-through). When on: no PII, no request bodies, headers, cookies, query strings or local variables, one-time link tokens redacted from URLs, no tracing. 7 tests with a fake SDK; never sent to a real Sentry. Not added to the web app (needs a heavier SDK and a decision on browser data).
- **Brand placeholders**: `app/icon.svg`, `app/apple-icon.tsx`, `app/opengraph-image.tsx` and one for `/products/vigilo`, rendered at build (checked: 1200x630 and 180x180 PNGs, viewed). They are placeholders from the brief in `brand.md`, not a logo.
- **Dependencies**: `npm audit --omit=dev` found a critical Next.js remote-code-execution advisory in `next/og` (the feature the new social images use) in 16.2.0 to 16.3.5; upgraded `next` and `eslint-config-next` to 16.4.0 and ran `npm audit fix` for `sharp` and `source-map-js`. Production audit is now clean. Remaining findings are dev-only (e.g. `braces`). Python dependencies were not audited.
- **Docs**: `docs/self-hosting.md` (Stripe instead of Paddle, real plans, new variables, deletion section) and the billing/organisation section of `docs/api.md` rewritten; other docs still mention Paddle in historical notes.

## Browser-test infrastructure (2026-10-09)
`apps/web/playwright.config.ts` (base URL localhost:3000, Clerk testing setup), `e2e/auth.ts`, `e2e/*.spec.ts`; `scripts/e2e-up.sh|down.sh|reset-db.sh` run the API (:8000, CORS for :3000), the scanner worker and a fresh `vigilo_e2e` database. Run: `./scripts/e2e-up.sh`, then in `apps/web`: `set -a; . ./.env.local; set +a; E2E_USER_EMAIL=<an existing dev-instance user> npx playwright test`. The specs create organisations, targets, invitations and audit events in that user's account: use a throwaway user.

## Ownership transfer (2026-10-09)
- `POST /v1/orgs/{id}/transfer-ownership` `{new_owner_account_id, confirm_slug}`: current owner only (admins and members 403, outsiders 404). The new owner must already be a member; the caller becomes an admin; `organizations.created_by` follows the owner so everything that reads it as "the owner" (the Stripe-webhook fallback, account deletion) stays true. Refused for personal workspaces (409), for yourself (422), for non-members (404), without the typed address (422).
- The organisation row is locked (`SELECT ... FOR UPDATE`) and the previous owner is demoted before the new one is promoted, because the database allows exactly one owner at every step. Proven, not assumed: a deterministic two-session test fails with a unique-index database error when the lock is removed and passes (a clean 403-style refusal) with it.
- Billing and limits stay with the organisation, not the person: its subscription, Stripe customer and plan are unchanged; the new owner manages them as an owner. The card on file is still whoever paid: change it in the portal.
- The old owner can then delete their account: the blocker message now says "hand the organisation to one of them, or remove them first".
- UI: members page, owner only, team organisations only: "Make owner" opens a confirmation that names the consequences and asks for the address; an audit sentence ("Handed the organisation to ...").
- **Bug found on the way:** `GET /v1/orgs/{id}/usage` took the scan limit from the owner's personal account plan, so a Pro team showed the free limit. It now uses the organisation's own plan (the quota's source).
- Tests: `test_ownership_transfer.py` (10) and browser spec S-TEAM-6.

- Update: the 4 object-storage tests pass against moto (784 passed, 0 failed). CI uses `moto_server` on :9000.

- 2026-10-10: renumbered. Production runs upstream's `0009_org_accounts` (revision `0009`, adds `accounts.clerk_org_id` and `contact_email`), so this branch's organisation migrations were moved from 0009-0016 to 0010-0017 behind it. Verified with real Alembic runs: a fresh database to head, and a simulated production database (at 0009, with 3 people and 1 org-owned account) to 0017: all accounts kept, Pro plan intact, one personal organisation and membership per account.
