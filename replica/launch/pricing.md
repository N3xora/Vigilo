# Pricing (2026-10-07)

## Competitor public pricing, read 2026-10-07
Read with a page-summarising fetch, not by eye. Re-check before publishing; one value below looks wrong.
| product | plan | price | limits | URL |
| --- | --- | --- | --- | --- |
| Snyk | Free | $0 | 5 projects, 100 Snyk Code tests/mo | https://snyk.io/plans/ |
| Snyk | Team | from $25/month | 100 projects, up to 10 developers | https://snyk.io/plans/ |
| Snyk | Enterprise | credit based, 1 credit = $1, quote | per developer/day and per target/day rates | https://snyk.io/plans/ |
| Aikido | Developer | $0 | 2 users, 10 repos | https://www.aikido.dev/pricing |
| Aikido | Basic | $300/month | 10 users, 100 repos | https://www.aikido.dev/pricing |
| Aikido | Pro | $600/month | 10 users, 200 repos | https://www.aikido.dev/pricing |
| Aikido | Advanced | $600/month (**same as Pro in my read: verify**) | 10 users, 500 repos | https://www.aikido.dev/pricing |
| Aikido | pentest | from $4,000 per assessment | | https://www.aikido.dev/pricing |
Both sell code and dependency scanning per seat or repo. Vigilo scans a live URL, a different job, so these are a price context, not a like-for-like.

## What reviewers said about price (`replica/feedback.md`)
1 comment of 8, one source, from 2017 ("$100/mo" for a dependency check). Not a trend. No billing or cancellation complaints were found, so none are claimed.

## Current model (already in the product and on onenexora.com)
- Vigilo: **Free** (1 target, 3 scans/month, passive checks) and **Pro $29/month or $290/year** (25 targets, unlimited scans, active checks, daily monitoring, API, white-label). Yearly saves $58 (about 17%, two months free is $58 exactly).
- Flat per account, not per seat. Annual 17% off.
- Cancelling: Stripe customer portal, no email or call. Renewal reminder emails are NOT built yet.
- Other Nexora products use a 5-tier ladder (Free, Starter, Pro, Business, Scale) with 20% annual discount (see `lib/nexora/catalog.ts`). Inconsistent with Vigilo's two tiers and 17%; pick one rule before launching a unified pricing page.
- The brief says three tiers at most per product. Vigilo has two; the others have five. Cut Sentinel/CSPM/Gateway to three before they leave beta.

## Stripe objects (you create these; test mode first)
Exists in code: `STRIPE_PRICE_ID_PRO` ($29/month) and `STRIPE_PRICE_ID_PRO_YEARLY` ($290/year).
Not built: per-product prices for Sentinel, CSPM and Gateway, the `product_slug` on checkout, and NeuraWall. Nothing was created in Stripe by me.

## Fix in the product
Done: portal-based cancel. To do: renewal email 7 days before charge, an explicit "your plan ends on {date}" after cancel, no seat-based jump (flat plan already guarantees this).
