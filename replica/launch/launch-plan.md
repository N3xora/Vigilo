# Launch plan

Status: **not launch-ready.** `replica/parity.md` verdict is not shippable (9 of 13 must-haves open), the console UI and landing page have never been rendered in a browser, and the name/domain questions in `replica/brand.md` are unresolved.

## Store listing
Not applicable: there is no mobile app, so there is no App Store or Play listing and `listing.py` has nothing to check. The nearest listing surfaces are the GitHub Marketplace entry for `.github/actions/scan` and a directory entry for the MCP server, both unwritten.

## Before anything public
1. Confirm you own vigilo.io, or move the support/abuse/security addresses and User-Agent URL to onenexora.com. Get a trademark search for both names.
2. Add Clerk keys, run `npx playwright test`, fix what breaks, check 390px and 1440px.
3. Wire per-product Stripe checkout (test mode), then live mode only at deploy.
4. Analytics and error tracking: none exist yet. Choose one of each; list them as processors in `/privacy`.
5. Beta list: a waitlist form is not built. Use plain email until it is.

## First 10 users (by hand)
People who ship apps from AI tools and have asked "is this safe?" in public. Find them in the threads you can read yourself: Hacker News "Show HN" posts for vibe-coded apps and the Supabase/Lovable communities. Offer the free scan and ask what they would do with the report. I did not search these communities, and I am not listing individuals.

## Post
Lead with the fix, not the product: "Most scanners flag a lot and prove little. This one only reports what it can show with a recorded request." Show one real scan of a site you own, with permission. Post on Show HN and Product Hunt only after item 2 and 3 are done. No reviewer quotes, no competitor names.

## Measure
Scans submitted, scan-to-signup, report views, fix-prompt copies, free-to-Pro conversion, cancellations with the reason. None are tracked yet.
