# Postmark setup

The app sends through Postmark's transactional API (`POST api.postmarkapp.com/email`, message
stream `outbound`, one server token, `From` = `MAIL_FROM_ADDRESS`). It sends account and invite
emails, scan reports, monitoring alerts and organisation invitations. All are transactional; there is no
marketing mail.

You do the account steps; I never enter tokens.

## 1. Account and server

1. Create a Postmark account and a **Server** named for production (for example `vigilo-production`).
2. Keep the default **Transactional** stream (`outbound`). Do not use the Broadcast stream.
3. New Postmark accounts start in test mode and can only send to addresses on the same domain.
   Ask Postmark to approve the account (their review form asks what you send and how recipients
   opt in) before expecting invitations to reach outside addresses.

## 2. Verify the sending domain

In **Sender Signatures → Domains → Add domain**, add `onenexora.com`. Postmark shows the records.
Add them at Squarespace exactly as shown:

| Record | Notes |
| --- | --- |
| DKIM (TXT, a `…._domainkey` name) | Copy name and value as shown. |
| Return-Path (CNAME, usually `pm-bounces`) | Gives you a verified return path and bounce handling. |
| SPF | **Merge, do not add a second record.** The domain's SPF today is `v=spf1 include:_spf.google.com ~all` (Google Workspace). It becomes `v=spf1 include:_spf.google.com include:spf.mtasv.net ~all`. Use the include Postmark shows if it differs. Two SPF records make both fail. |
| DMARC (TXT at `_dmarc`) | `v=DMARC1; p=none; rua=mailto:<your address>` to begin with. Tighten to `quarantine` after a few weeks of clean reports. |

Click **Verify** on each record in Postmark. Do not change the Google MX records.

## 3. Sender address

`MAIL_FROM_ADDRESS=scans@onenexora.com`. Add it as a sender signature if Postmark asks, and
create the mailbox or alias in Google Workspace so replies and bounces land somewhere. Also create
`support@`, `abuse@` and `security@onenexora.com`; the product publishes them.

## 4. Server `.env`

```
POSTMARK_SERVER_TOKEN=<the server token from Postmark's API Tokens tab>
MAIL_FROM_ADDRESS=scans@onenexora.com
```

Restart the api and scanner containers after changing it (`./scripts/deploy.sh`).

## 5. Check it

1. Postmark's own **Send test email** on the server page, to an address you control.
2. In the app: invite a second address you own from `/console/members`, and confirm the email
   arrives in the inbox, not spam, and that the link opens the accept page.
3. In Gmail, open the message → **Show original**: SPF, DKIM and DMARC should all say PASS.
4. Watch Postmark's **Activity** for bounces and spam complaints in the first week. A bounce rate
   above a few percent puts the account at risk.

## Limits worth knowing

- Invitations are rate-limited per address per day in the app, so a retry loop cannot flood a
  recipient.
- Until `MAIL_FROM_ADDRESS`'s domain is verified, Postmark rejects every send. For invitations the
  app reports the email status as `failed` to the caller and carries on; the invitation is still
  created and can be copied as a link. The failure is **not logged by the app**, so watch
  Postmark's Activity page rather than the API logs.

## Exact records for onenexora.com

Squarespace asks for Host, Type and Data. Two of these records are unique to your Postmark
account (the DKIM selector and key), so Postmark's **Sender Signatures → onenexora.com → DNS
Settings** page is the source for those; the others are fixed.

| # | Host | Type | Data | Source |
| --- | --- | --- | --- | --- |
| 1 | `@` | TXT | `v=spf1 include:_spf.google.com include:spf.mtasv.net ~all` | **Edit the existing** `v=spf1 include:_spf.google.com ~all` record; do not add a second SPF TXT. |
| 2 | `<selector>._domainkey` | TXT | `k=rsa;p=<long public key>` | Copy both the host and the value from Postmark. The selector looks like `20260101000000pm`; yours is different. Paste the key as one string with no line breaks or spaces. |
| 3 | `pm-bounces` | CNAME | `pm.mtasv.net` | Fixed. Gives Postmark's Return-Path. |
| 4 | `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:security@onenexora.com` | Fixed; the reports go to a mailbox you control. Postmark also offers a free weekly DMARC digest: if you use it, replace the `rua` address with the one it gives you. |

Leave alone: the Google MX record, the `google-site-verification` TXT, and the five Clerk CNAMEs
(`clerk`, `accounts`, `clkmail`, `clk._domainkey`, `clk2._domainkey`). The Clerk DKIM names are
`clk` and `clk2`, so they do not clash with Postmark's selector.

Squarespace specifics: enter the host without the domain (`pm-bounces`, not
`pm-bounces.onenexora.com`), keep TTL at its default, and make sure the SPF edit saves as a single
record.

## Check each record

```bash
dig +short TXT onenexora.com | grep spf1          # one line, containing both includes
dig +short TXT <selector>._domainkey.onenexora.com | cut -c1-60   # starts with "k=rsa;p="
dig +short CNAME pm-bounces.onenexora.com          # pm.mtasv.net.
dig +short TXT _dmarc.onenexora.com                # the DMARC line
```

When all four answer, press **Verify** on the DKIM and Return-Path rows in Postmark. SPF and DMARC
are checked from the message headers on the first real send (Gmail → Show original → PASS).
