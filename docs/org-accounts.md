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

Billing (checkout and the customer portal) in an org account requires the
`org:admin` role; a missing role fails closed. Personal accounts are unaffected.

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
