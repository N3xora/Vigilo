# Landing page (built at `/products/vigilo`; `/` is now the Nexora home, 2026-10-08)

Angle: A from `replica/fixes.md` (evidence: false positives, 4 comments, 1 source; thin). Voice: plain, specific, calm (`replica/brand.md`).

Implemented in `apps/web/app/page.tsx` (hero) and `apps/web/components/marketing/LandingSections.tsx` (sections). The scan form stays the one button.

1. Hero: "Other scanners bury you in alerts. {brand} shows only what it can prove." + one line + the scan form.
2. Problem: a pile of unproven alerts, and the repeat mistakes of AI-built apps (paraphrased, no reviewer quotes).
3. How it works: paste URL, we check what we can prove, paste the fix.
4. What you get: proof not guesses, honest about gaps, fixes you can paste, accept a risk once, regression catching, pipeline fit (CLI, GitHub Action, API, MCP).
5. Pricing: Vigilo Free and Pro from `lib/nexora/catalog.ts`, link to /pricing.
6. FAQ: code access, safety of scans, what is checked (64 checks, counted from the catalog), fix quality, cancelling.
7. Final call to action scrolls to the form.

Rules kept: no testimonials, no user counts, no logos, no star ratings, no competitor names. The proof row is intentionally absent until real beta users give permission.
Claims to keep true: "64 checks" (recount when the registry changes), "cancel from the billing page" (Stripe portal), "accept a risk" (suppressions; org-wide acceptance is not built), "scheduled re-scans" (Pro). Features from the fix plan (top-3 summary, stack-aware context) are NOT claimed because they are not built.
Status: lint, typecheck and `next build` pass. Not rendered in a browser (no Clerk keys), so layout, 390px/1440px and keyboard behaviour are unverified.
