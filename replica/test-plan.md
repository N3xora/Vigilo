# Test plan (2026-10-07)

Legend: A = automated and passing, S = automated but skipped (needs Clerk dev keys), M = manual, not run, - = not built yet.

| case | flow | what | status |
| --- | --- | --- | --- |
| F01-H1 | F01 visitor | /pricing lists 5 products; annual toggle shows $290/yr for Vigilo | S |
| F01-H2 | F01 | /products shows Live / Beta / Coming soon badges | S |
| F01-E1 | F01 | no horizontal scroll at 390px and 1440px | S |
| F01-E2 | F01 | billing interval reachable and switchable by keyboard | S |
| F01-A1 | F01 | axe WCAG A/AA scan of /pricing and /products | S |
| F01-H3 | F01 | anonymous Vigilo scan to report | existing Vigilo suite, A (backend); browser M |
| F02-H1 | F02 sign up | first GET /v1/orgs provisions exactly one personal org | A |
| F02-E1 | F02 | two tabs on first sign-in, concurrent provisioning, no 500 | A (was B1) |
| F02-E2 | F02 | blank and 201-char org name rejected | A (was B2) |
| F02-E3 | F02 | emoji and accents in org name round trip | A |
| F02-N1 | F02 | duplicate slug 409, invalid slug 422 | A |
| F02-N2 | F02 | malformed org id 422, unknown org 404 | A |
| F02-S1 | F02 | second user's org invisible on every route (404) | A |
| F03-H1 | F03 activate | list products, enable Sentinel | A |
| F03-E1 | F03 | enable twice (double click) is idempotent | A |
| F03-N1 | F03 | unknown product 404 | A |
| F03-N2 | F03 | viewer cannot enable (403) | A |
| F04-H1 | F04 upgrade | per-product checkout and webhook | - not built |
| F04-N1 | F04 | declined card `4000 0000 0000 0002` | - needs Stripe test keys |
| F05-H1 | F05 invite | invite, accept, member listed | A |
| F05-E1 | F05 | removed member loses access at once | A |
| F05-E2 | F05 | invite is single use | A |
| F05-N1 | F05 | malformed invite email 422 | A (was B3) |
| F05-N2 | F05 | expired invite 410 | A |
| F05-N3 | F05 | accept while already a member 409, role unchanged | A |
| F05-N4 | F05 | invite addressed to another email cannot be accepted | A |
| F05-N5 | F05 | viewer and member role gates (403) | A |
| F05-N6 | F05 | admin cannot mint, change or remove the owner | A |
| F05-R1 | F05 | viewers may read members, products, usage | A (was B4) |
| F06-H1 | F06 org API keys | org-scoped keys with product scopes | - not built |
| F07-H1 | F07 monitoring | alert on regression | existing Vigilo suite, A |
| U1 | usage | 10 concurrent increments sum to 10 | A |
| U2 | usage | Vigilo limit comes from owner's plan (free = 3) | A |
| M1 | migration | 0009 backfill on populated DB, downgrade, upgrade, `alembic check` | A (manual run, not in CI) |
| M2 | console UI | /console, /console/usage, /console/members render and are keyboard usable | M, needs Clerk keys |
| M3 | email | invite email delivered | - not built |
| M4 | offline / slow network, screen reader pass | | M, not run |

Not covered: time-zone behaviour of the usage period (UTC month only, covered by logic, no boundary test); account deletion with owned orgs (see To check).
