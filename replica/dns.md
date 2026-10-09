# Domain and DNS records

> **Decision 2026-10-10: the web host is `vigilo.onenexora.com`** (matching the domain already chosen on
> `origin/main`), not `app.onenexora.com`. Wherever the text below says `app.onenexora.com`, read
> `vigilo.onenexora.com`. **DNS action:** add an A record `vigilo` → `92.5.69.99` (the `app` record is no
> longer needed). The API host is still undecided: `vigilo-api.onenexora.com` is occupied by something else.

No domain has been chosen yet, so this uses a proposal built on `onenexora.com`, which you
said is your platform site. Swap in your own names if you decide differently. Anything in
`<angle brackets>` is a value only you can get (your VPS, Clerk, Postmark).

## What I found for 92.5.69.99 (2026-10-09, public lookups and plain GETs only)

- `onenexora.com` and `api.onenexora.com` already resolve to 92.5.69.99. `app.onenexora.com` has no record yet.
- Ports 22, 80 and 443 answer, and **a Caddy already serves both names** (`via: 1.1 Caddy`; a Let's Encrypt certificate for `api.onenexora.com` was issued 2026-09-26). `https://api.onenexora.com/healthz` returns 404, so that name is **not** this app's API; it belongs to something else.
- DNS is hosted at Squarespace (`nsd1-4.squarespacedns.com`). Mail is Google Workspace: MX `smtp.google.com`, SPF `v=spf1 include:_spf.google.com ~all`.

What that changes:
1. **Do not start this repo's bundled Caddy on that VPS.** It would fight the existing Caddy for ports 80 and 443. Use the external-proxy mode (`docs/self-hosting.md`, "Behind an existing reverse proxy") and add two site blocks to the Caddy that already runs.
2. **Do not reuse `api.onenexora.com`** unless you intend to replace whatever it serves. Suggested: `app.onenexora.com` (web) and `vigilo-api.onenexora.com` (this API).
3. **Postmark SPF must be merged, not added.** There is already one SPF record, so it becomes `v=spf1 include:_spf.google.com include:spf.mtasv.net ~all` (check the exact include Postmark shows you).

## Proposal

| Role | Hostname | Why |
| --- | --- | --- |
| Web app (`WEB_DOMAIN`) | `app.onenexora.com` | The existing site at the apex keeps working; the platform shell moves to the apex later, once you are ready. |
| API (`API_DOMAIN`) | `api.onenexora.com` | Separate hostname so Caddy can route and CORS stays an exact match. |
| Mail sender (`MAIL_FROM_ADDRESS`) | `scans@onenexora.com` | Postmark must verify a domain you control. `vigilo.io` is not verified as yours. |

Env values: `WEB_DOMAIN=app.onenexora.com`, `API_DOMAIN=api.onenexora.com`,
`WEB_APP_URL=https://app.onenexora.com`, `PUBLIC_API_BASE_URL=https://api.onenexora.com`,
`MAIL_FROM_ADDRESS=scans@onenexora.com`.

## Records at your DNS provider

| Type | Name | Value | Notes |
| --- | --- | --- | --- |
| A | `app` | `92.5.69.99` | Caddy issues the certificate itself. |
| A | `vigilo-api` (or `api`, see above) | `92.5.69.99` | Same. |
| AAAA | `app`, `api` | `<VPS IPv6>` | Only if the VPS has one. |
| CNAME / TXT | as Clerk shows | `<Clerk values>` | Clerk production instance: a frontend-API CNAME, an accounts CNAME and email DKIM CNAMEs. Copy them from Clerk's DNS page exactly. |
| TXT | `@` or as shown | `<Postmark SPF value>` | SPF; if the domain already has an SPF record, merge into it, never add a second one. |
| TXT / CNAME | as shown | `<Postmark DKIM value>` | DKIM. |
| CNAME | as shown | `<Postmark Return-Path value>` | Return-Path. |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:<you>@onenexora.com` | Start at `p=none`, move to `quarantine` once the reports are clean. |

Do not touch the existing records for the apex and `www`.

## VPS prerequisites

Ports 80 and 443 open (Caddy needs both for the certificate challenge), Docker with Compose v2,
and DNS pointing at the VPS before the first `scripts/deploy.sh`, otherwise certificate issue fails
and Let's Encrypt rate-limits retries.

## Check each step

```bash
dig +short A app.onenexora.com          # the VPS IP
dig +short A api.onenexora.com          # the VPS IP
dig +short TXT _dmarc.onenexora.com     # the DMARC value
dig +short TXT onenexora.com | grep spf # exactly one SPF record
curl -sI https://api.onenexora.com/healthz | head -1   # after deploy: HTTP/2 200
```

## Done: addresses moved to onenexora.com (2026-10-09)

`brand.config.json` (domain, support@, abuse@, security@), `SECURITY.md`, `.env.example` and
the compose default now use `onenexora.com`. The scanner User-Agent now points at
`https://app.onenexora.com/aup` (the acceptable-use page; there is no separate scanner page), in
all six probe files and the ownership check. The SARIF tool URI is
`https://app.onenexora.com/products/vigilo`. Test fixtures that use `vigilo.io` as fake data were
left alone.

Create these mailboxes or aliases before launch, or mail to them bounces: `support@`, `abuse@`,
`security@` and `scans@onenexora.com`. Check that `app.onenexora.com/aup` is live after deploy,
because site owners will see that URL in their logs.

## Caddy on the existing VPS

`Caddyfile.external-proxy.example` has the two site blocks (`app.onenexora.com` and
`vigilo-api.onenexora.com`), with both ways for the existing Caddy to reach the app: loopback
ports if Caddy runs on the host, container names if it runs in Docker. On the server, set in
`.env`:

```
COMPOSE_FILE=docker-compose.self-host.yml:docker-compose.external-proxy.yml
WEB_APP_URL=https://app.onenexora.com
PUBLIC_API_BASE_URL=https://vigilo-api.onenexora.com
```

`WEB_DOMAIN` and `API_DOMAIN` go unused in this mode. The Stripe webhook URL becomes
`https://vigilo-api.onenexora.com/v1/billing/webhook`, and the Clerk production instance gets
`https://app.onenexora.com` as its allowed origin.

## Status check, 2026-10-09 (public lookups, no credentials)

| Item | State |
| --- | --- |
| `app.onenexora.com` | **no record yet** (needed for the web app) |
| `vigilo-api.onenexora.com` | resolves to 92.5.69.99; `/healthz` answers `{"status":"ok"}` with a certificate issued 2026-09-26, but `/v1/orgs` returns 404 where this repo's API returns 401. **Something else already answers there** (possibly an older Vigilo deployment). Check `docker ps` on the VPS before reusing the name. |
| Clerk production | records exist for the **apex** `onenexora.com` (`clerk`, `accounts`, `clkmail`, `clk._domainkey`, `clk2._domainkey`) and the JWKS at `https://clerk.onenexora.com/.well-known/jwks.json` returns 200. So the instance was created on the apex, not on `app.` |
| Postmark DKIM / Return-Path | not found |
| SPF | unchanged: `v=spf1 include:_spf.google.com ~all` (Postmark not merged yet) |
| DMARC | not found |
