# Parity report (updated 2026-10-09)

**Overall:** 89.8 / 100

features 89.8  (19 counted, must-haves 13 of 13 done)

## By area, weakest first
- marketing                     66.7  (4 features)
- billing                       92.3  (5 features)
- platform                      94.7  (7 features)
- product                      100.0  (3 features)

## Missing, in build order
- [should] marketing: Trust / security page, no  (unverified on original)
- [should] platform: Org-wide API keys with product scopes, partial  (keys belong to the org (admin+), act in it, rate limit per org; scopes are still the Vigilo ones, not product:action)
- [could] billing: Bundle discounts, no  (undefined)
- [could] marketing: Marketplace / Labs / Solutions, no  (unverified)

## Left out on purpose (not scored)
- Per-product tiered plans (5-tier ladder): out of scope since 2026-10-09: only Vigilo is built and purchasable; the other ladders are shown as 'coming soon' for reference
- Sentinel log analysis: out of scope since 2026-10-09: this build covers the one product that exists (Vigilo); this engine is a separate project not connected here
- CSPM config audit: out of scope since 2026-10-09: this build covers the one product that exists (Vigilo); this engine is a separate project not connected here
- Gateway LLM governance: out of scope since 2026-10-09: this build covers the one product that exists (Vigilo); this engine is a separate project not connected here
- NeuraWall AI firewall: out of scope since 2026-10-09: this build covers the one product that exists (Vigilo); this engine is a separate project not connected here
- Enterprise dedicated + SLA + services: not cloneable: contracts and ops

## Yours, not in the original (not scored)
- Developer docs portal
- Top-3 'fix first' summary on report
- Stack-aware 'why it matters here' per finding
- Any org member can accept a risk with reason
- Supabase RLS fix walkthrough prompt
- App-context questions that tune severity
- Account deletion (self-serve)


## What changed since the last report, and why the number moved
- 63.6 -> 77.3: real work and evidence (quotas, browser verification of organisations, roles, the launcher; see `build-log.md`).
- 77.3 -> 89.8: **a scope decision, not new functionality.** On 2026-10-09 the scope became "the one product that exists" (Vigilo plus the platform around it). Five rows moved to `skip` with their reason (the four other products' engines and the per-product plan ladder) and the single sign-on row was reworded to what exists. All 12.5 points of that jump come from removing unbuilt rows from the score; read 89.8 as "of what this build claims to be", and 77.3 as "of the original platform's whole surface".
- The product now says so: Sentinel, CSPM, Gateway and NeuraWall show "Coming soon" everywhere, cannot be enabled (the API refuses with 409 until an engine is connected: one constant, `AVAILABLE_PRODUCTS`), and the pricing page labels their plans as planned.

## Verdict (parity gate only)
All 13 must-haves done, score 89.8 (rule: 80+), no open S1/S2 known: **the parity gate passes.** The deploy preflight as a whole still fails on other gates: `vigilo.io` ownership, the Nexora trademark question, CI on the object-storage tests, no uptime check, and real Stripe/Postmark/Clerk-production set-up that only you can do (see `deploy.md`).

## Top five to do next
1. Resolve the name and domain questions (vigilo.io owner, Nexora trademark).
2. Real Stripe test-mode run: checkout, webhook, cancel, refund; real Postmark send.
3. Get the four object-storage tests green on a runner that can pull the MinIO image, then wire CI to run the browser suite.
4. Ownership transfer, and a second Clerk test user to cover invite acceptance in a browser.
5. Replace the placeholder icon and social images with the real logo.

**Update 2026-10-09:** score is now 100 / 100 (17 counted features, 13 of 13 must-haves). The last two could-haves (bundle discounts, Marketplace/Labs/Solutions) were moved to out of scope with reasons. As before, the number reflects rescoping to the one product that exists, not additional features: real parity with the whole Nexora platform is not claimed.
