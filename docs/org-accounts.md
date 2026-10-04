# Organisation-owned accounts

A Vigilo `Account` is either **personal** (one Clerk user, the original model)
or **organisation-owned** (one Clerk organisation shared by its members, so a
team has one plan, one set of targets and one set of API keys).

## How a request resolves

`require_account` verifies the Clerk token, then:

1. token has an `org_id` claim → the account for that organisation
   (`accounts.clerk_org_id`), created free on the first request made inside it;
2. otherwise → the caller's personal account, exactly as before.

An org account's `email` is a synthetic, never-deliverable
`<org_id>@org.vigilo.invalid` (the column is unique and non-null).
`contact_email` — the first acting member's email — is where notifications and
Stripe receipts go (`Account.notification_email`).

## Billing

Organisation accounts are billed by **NEXORA Core**, not by Vigilo: Vigilo's checkout and
portal return `409` with a `billing_url` pointing at NEXORA Console. Core records the Stripe
subscription (the same Pro prices Vigilo sells) and then tells Vigilo the plan with
`POST /v1/internal/org-plan`, signed with HMAC-SHA256 over `"<unix-seconds>.<raw body>"` using
the shared `NEXORA_SYNC_SECRET` (replay window 5 minutes, constant-time comparison, 404 until
the secret is set, identical 401 for every signature failure). A paid plan creates the
organisation's account if it does not exist yet; a downgrade for an organisation Vigilo has
never seen changes nothing. The call is idempotent. Personal accounts keep Vigilo's own
checkout and portal, unchanged.

## Rollout

The code is inert until the token carries the org claim. In the Clerk
dashboard, edit the `vigilo-api` JWT template to add:

```json
{ "email": "{{user.primary_email_address}}", "org_id": "{{org.id}}", "org_role": "{{org.role}}" }
```

(keep your existing claims). Until then every session resolves to its personal
account. Existing personal accounts, subscriptions and API keys are not moved:
when a user starts acting inside an organisation they see that organisation's
own (initially free) account. Migrating a personal subscription into an
organisation is a deliberate, separate step.

## Rollback

Remove `org_id`/`org_role` from the template and every session is personal
again; nothing else needs to change. The migration (`0009`) only adds two
nullable columns and a unique constraint, and its downgrade drops them.
