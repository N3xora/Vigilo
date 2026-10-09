# Clerk production instance

You do the account steps; I never enter keys. This is the exact list, built from what the app
needs and from the dev instance's JWT template (read-only).

> **Status 2026-10-09:** the instance was created on the apex `onenexora.com` (DNS records and the JWKS at
> `clerk.onenexora.com` are live). That works; the session cookie then covers subdomains, including `app.`.
> Set `CLERK_JWKS_URL=https://clerk.onenexora.com/.well-known/jwks.json`, allow `https://vigilo.onenexora.com`
> as an origin, and make sure the `vigilo-api` JWT template exists in this instance.

## 1. Create the production instance

In the Clerk dashboard, open the application and choose **Create production instance**.
Clone settings from development when offered.

- **Domain:** use `vigilo.onenexora.com`. The session cookie then stays on `app.` and the existing
  site on the apex is untouched. (If you pick the apex instead, the cookie covers every
  subdomain, including the other site.)
- Production needs a domain you own; the `*.clerk.accounts.dev` domain is development only.

## 2. DNS records at Squarespace

Clerk shows the exact records after step 1. They are CNAMEs for the frontend API, the account
portal, and mail DKIM/return-path (typically `clerk`, `accounts`, `clkmail` and two `*._domainkey`
names under your domain). Copy them as shown, wait for Clerk's **Verify** to go green (propagation
can take minutes to a few hours), and do not proxy or flatten them.

## 3. Match the app's configuration

| Setting | Value | Why |
| --- | --- | --- |
| JWT template, name | `vigilo-api` | `NEXT_PUBLIC_CLERK_JWT_TEMPLATE` and the API both use this name. |
| JWT template, claims | `{"email": "{{user.primary_email_address}}"}` | The API reads `email` from the token. This is the dev template's only claim. |
| JWT template, lifetime / skew | 60 seconds / 5 seconds | Same as dev. |
| Sign-in identifiers | Email address | The app identifies people by email. |
| Allowed origin | `https://vigilo.onenexora.com` | Production browser requests. |
| Organizations (Clerk's feature) | leave off | Organisations, roles and invites are the app's own. |

If the production template is not created, every signed-in API call returns 401.

## 4. Keys and the JWKS URL

From the production instance's **API keys**:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` = the `pk_live_…` key
- `CLERK_SECRET_KEY` = the `sk_live_…` key
- `CLERK_JWKS_URL` = `https://clerk.onenexora.com/.well-known/jwks.json`, but use the
  frontend API host Clerk shows for your instance; the publishable key encodes it (base64 after
  `pk_live_`).

Put these in the server's `.env` only. The publishable key is baked into the web build, so
**rebuild the web image after changing it** (`./scripts/deploy.sh`).

## 5. Check it

```bash
# the JWKS answers 200 and lists keys
curl -s -o /dev/null -w "%{http_code}\n" "$CLERK_JWKS_URL"
# after deploy: the sign-in page loads and a sign-up works end to end
curl -sI https://vigilo.onenexora.com/sign-in | head -1
```

Then sign up once with your own email, open `/console`, and confirm the API call succeeds (no
401). The first sign-in creates your account and personal workspace.

## 6. Do not

- Point the browser test suite or CI at production keys. CI keeps the **development** instance
  (`E2E_CLERK_*` secrets); `@clerk/testing` sign-in by email is not for production.
- Reuse the development users or keys. They are separate instances.
