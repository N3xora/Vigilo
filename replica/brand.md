# Brand (2026-10-07)

There is no third-party app to rebrand away from: Nexora (platform) and Vigilo (first product) are already your names. This pass checks whether those names are safe to launch under, sets the palette, voice and logo brief, and sweeps for competitor leftovers. **These are screening checks, not legal clearance.**

## 1. Name checks, run today

| name | check | result (2026-10-07) |
| --- | --- | --- |
| Nexora (platform) | web search, "Nexora cybersecurity platform" | **Conflict risk.** A Capterra listing shows a product called Nexora, a security platform for non-human identities (service accounts, API tokens, cloud roles). Same category, same name. https://www.capterra.com/p/10036589/Nexora/ |
| Nexora | domains | nexora.com is taken (registered 2013, GoDaddy). onenexora.com is registered to you (created 2026-09-20, Squarespace). |
| Nexora | USPTO / EUIPO / WIPO / Canada | **to run** |
| Vigilo (product) | web search | Different companies use near-identical names in security: VigiloSec (managed detection and response) and Vigilos, Inc. (physical/operational security software, Seattle, since 2000). https://www.crunchbase.com/organization/vigilosec , https://www.cbinsights.com/company/vigilos |
| Vigilo | domains | vigilo.com taken (2002). **vigilo.io was registered 2024-06-14, before this repo existed, and it serves a live site (HTTP 301 from an nginx host on AWS). I cannot tell who owns it.** |
| Vigilo | USPTO / EUIPO / WIPO / Canada | **to run** (classes 9 and 42) |
| Vigilo | App Store, Play, X, GitHub, Instagram, TikTok | **to run** |

### What this means
1. **Confirm you own vigilo.io.** `brand.config.json`, `SECURITY.md`, `docker-compose.self-host.yml` and `.env.example` point support@, abuse@ and security@ addresses, the scanner's User-Agent URL and the DNS-verification key at `vigilo.io`. If it is not yours, those addresses and the "+https://vigilo.io/scanner" link in every scan request go to a stranger. If it is yours, ignore this. I did not change anything.
2. **"Nexora" is the bigger name risk**: a same-category product already sells under it. Before spending on the brand, get a proper trademark search from a lawyer in your market.
3. Alternatives already held in the README: **Prooflight** (prooflight.io shows "not found" in whois today, prooflight.com is taken since 2016), **Latch** (latch.io taken), **Bezpiecznik**. Prooflight.io being unregistered is a lead, not clearance; the trademark and app-store checks above are still to run for it.

## 2. Palette
Kept as set in `replica/design/tokens.json` (derived from the repo's own theme, no third-party colours): slate neutrals, teal accent `#0E7490` on light, `#22D3EE` on dark. Contrast: 17 light pairs and 12 dark pairs, 0 AA failures. No competitor brand hex was added to `brand.json` because I could not verify their exact values; the sweep checks names and domains only.

## 3. Logo brief
- Idea: a lens or checkpoint that stays steady while findings move around it. The angle is "reports only what it can prove".
- Mark: symbol plus wordmark. Must read at 16px (favicon) and as a 1024px app icon.
- Deliverables: SVG, 1024x1024 icon with no transparency for iOS, favicon set, 1200x630 social image.
- Must not resemble another security brand's mark. Put the drafts next to the logos of Nexora (the Capterra product), Vigilos and VigiloSec and check shape, colour pair and letterform.
- Nothing is made yet. `apps/web/public/` has no logo or icon.

## 4. Voice
Three words:
- **Plain**, not casual: say "your database is readable by anyone" and skip "critical misconfiguration".
- **Specific**, not exhaustive: one named problem with the request that proved it, not a wall of alerts.
- **Calm**, not soft: give severity honestly, no alarm and no reassurance the evidence can't back.

Do / don't:
| do | don't |
| --- | --- |
| "Anyone can read your users table." | "Potential data exposure detected." |
| "We couldn't check this, here is why." | silently count it as passed |
| "Paste this into your AI tool." | "Remediate per OWASP A05." |
| "Fix these 3 first." | a 40-item list in one colour |
| "No targets yet. Add the first site you want watched." | "Nothing to see here!" |

Strings: the existing UI copy ("Scan it", "Starting scan…", "No targets yet.", "No API keys yet.") is already plain and your own, so I left it alone. Add an action to the two empty states when `EmptyState` replaces them (e.g. "Add your first target").

## 5. Sweep
`python3 replica/sweep.py . --config replica/brand.json` reports **clean** for: Snyk, Aikido, Wiz, Talonwatch, CodeSlick, CodeShield and the domains snyk.io, aikido.dev. These are the competitors named in `replica/fixes.md`, so none of their names leaked into code, filenames or copy. Not checked by eye: favicon, OG image, email templates and app icon do not exist yet.
