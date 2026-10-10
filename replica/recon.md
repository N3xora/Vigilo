# Recon map: Nexora platform shell

Date: 2026-10-07. Not a competitor clone: both sources are the user's own. "Original" = onenexora.com (public marketing site, 2026-10-07) plus this repo (Vigilo, already built). "Clone" = the Nexora platform shell that hosts Vigilo and four other products.

## 1. Scope
- App/platform: web (Next.js console) + FastAPI backend. Matches the existing repo stack.
- Slice: platform shell only (one account, org, billing, API keys, product launcher, usage). Vigilo is product #1, already shipped. Other products start as stubs.
- Audience: DevOps / security engineers / AI-infra leads in multi-product environments (per onenexora.com).
- Terms: no third-party account used. Public pages only plus the owner's own repo.

## 2. Sources
| source | URL | gave us |
| --- | --- | --- |
| Home | https://onenexora.com | positioning "Build. Secure. Operate.", "one account, one console, one API surface", nav IA |
| Products | https://onenexora.com/products | 5 products, all Beta, categories AI/Security/Cloud/Developer |
| Pricing | https://onenexora.com/pricing | per-product tiers (below) |
| Developers | https://onenexora.com/developers | 404, so dev portal/docs not live |
| Repo docs | docs/*.md, docs/adr/* | Vigilo data model, API, roadmap, ADRs |
| Repo code | apps/web, apps/api, packages/* | existing screens, billing, identity |
| ChatGPT share | chatgpt.com/share/6ac652fc-... | NOT READABLE (title only: "Analiza repo VIGILO"). Needs pasted text. |
| Not fetched | /products/{sentinel,cspm,gateway,neurawall}, /platform, /marketplace, /solutions, /labs, /trust | next recon pass |

Reference screenshots: none captured yet (`replica/screens/` empty). Do with the in-app browser at human speed.

## 3. Screen inventory
Marketing (onenexora.com; not in repo yet unless noted)
| ID | screen | route | purpose | states |
| --- | --- | --- | --- | --- |
| S01 | Home | / | pitch, 3 pillars, CTAs Explore products / Get started / Talk to us | default |
| S02 | Products index | /products | filter All/AI/Security/Cloud/Developer | filtered, empty filter |
| S03 | Product detail x5 | /products/{slug} | per-product pitch + CTA | beta badge |
| S04 | Pricing | /pricing | per-product plan tables, monthly/annual (20% or 17% off) | monthly, annual |
| S05 | Platform | /platform (guess) | identity, orgs, API, billing, telemetry | unverified |
| S06 | Marketplace / Solutions / Labs | guess | unverified | unverified |
| S07 | Trust | guess | security transparency | unverified |
| S08 | Developers | /developers | 404 on the live site | missing |
| S09 | Legal: terms, privacy, cookies, AUP | /terms /privacy /cookies /aup | exists in repo (apps/web/app) | done |

Console / Vigilo (in repo)
| ID | screen | route | purpose | states seen |
| --- | --- | --- | --- | --- |
| S10 | Vigilo landing + scan form | apps/web/app/page.tsx | anonymous free scan | idle, submitting, error |
| S11 | Sign in / Sign up | /sign-in, /sign-up | Clerk | default |
| S12 | Dashboard | /dashboard | overview | empty, filled |
| S13 | Targets | /dashboard/targets | targets + ownership verification panel | empty, unverified, verified |
| S14 | Billing | /dashboard/billing | Stripe checkout and portal | free, pro |
| S15 | API keys | /dashboard/api-keys | create (plaintext once), revoke | empty, filled |
| S16 | Branding | /dashboard/branding | white-label (Pro) | locked, editable |
| S17 | Report | /reports/[scanId] | score, findings, evidence, PDF | passed/skipped sections, print mode |
| S18 | Share view | /share/[token] | public report | valid, revoked (410) |
| S19 | Monitoring | /targets/[id]/monitoring | history chart, alerts, badge embed | no monitor, active |

Needed for the shell (do not exist yet)
| ID | screen | purpose |
| --- | --- | --- |
| S20 | Org switcher + create org | multi-tenant root |
| S21 | Product launcher (home console) | tiles for all 5 products, status, usage |
| S22 | Members and roles | invite, RBAC |
| S23 | Unified billing | per-product subscriptions in one view |
| S24 | Org-wide API keys | one key surface, per-product scopes |
| S25 | Usage and quotas | scans/requests vs plan, per product |
| S26 | Audit log | org-level events (Vigilo already has audit_events) |
| S27 | Stub product pages x4 | Sentinel, CSPM, Gateway, NeuraWall: paste-in tool or "coming soon" |

## 4. Flows
- F01 Visitor to first value: S01 -> S02 -> S03(vigilo) -> S10 scan -> S17 report. Happy path 4 clicks. Edge: denied/denylisted URL, rate limit, scan timeout.
- F02 Sign up to console: S01 -> S11 -> S20 create org -> S21 launcher. Target: 3 clicks.
- F03 Activate a product: S21 -> product tile -> S13 add target -> verify ownership -> scan -> S17.
- F04 Upgrade: S04 or S14 -> Stripe checkout -> webhook -> entitlement change. Edge: webhook replay, cancel, downgrade.
- F05 Invite teammate: S22 -> invite -> accept -> role applied.
- F06 Automate: S24 create key -> CLI / GitHub Action / MCP -> S17.
- F07 Monitor regression: S19 enable monitor -> alert email -> S17.
- F08 Share report: S17 -> create share link -> S18.

## 5. Components (existing in apps/web/components)
Header, Footer, DraftBanner, ScanSubmitForm, DashboardNav, TargetsManager/TargetRow, VerificationPanel, UpgradeButton, ManageSubscriptionButton, ApiKeysManager, BrandingForm, ReportView, ScoreHeader, SeverityGroup, FindingCard, EvidencePanel, AgentPromptBlock, Passed/Skipped/AcceptedRisks sections, ExportPdfButton, ShareLinkManager, MonitorPanel, ScoreHistoryChart, AlertTimeline, BadgeEmbed.
Missing for the shell: OrgSwitcher, ProductTile, PlanTable (monthly/annual toggle), UsageMeter, MemberTable, RoleSelect, AuditTable, Toast, EmptyState.

## 6. Inferred data model
Existing (high confidence, docs/data-model.md): accounts, subscriptions, api_keys, branding_profiles, projects, targets, ownership proofs, scans, findings, reports, share_links, monitors, alerts, audit_events, remediation_cache.
Needed for the shell (proposed, medium confidence):
- Organization(id, name, slug, owner_account_id). Today everything keys on `account_id`, one project per account.
- Membership(org_id, account_id, role owner|admin|member|viewer).
- ProductEnablement(org_id, product_slug, status, enabled_at).
- Subscription(org_id, product_slug, plan_id, interval month|year, provider_subscription_id, status, current_period_end). Today it is a single account-level plan.
- UsageEvent / UsageCounter(org_id, product_slug, meter, period, count).
- ApiKey gains org_id and product-scoped scopes.
Gap: account-to-org migration. Clerk Organizations is the natural fit (clerk-orgs skill).

## 7. Pricing observed (onenexora.com, monthly / annual)
- Sentinel: Free 20 scans; Starter $9 150; Pro $29 1,500; Business $79 7,500; Scale $249 40,000 (annual = 20% off).
- CSPM: Free 10; Starter $19 75; Pro $49 750; Business $149 3,500; Scale $399 20,000.
- Gateway: Free 100 req; Starter $19 1,500; Pro $59 12,000; Business $199 60,000; Scale $599 300,000.
- Vigilo: Free (1 target, 3 scans, passive); Pro $29 / $290yr (25 targets, active checks, daily monitoring, API, white-label). Matches repo commit 4ad92bf.
- NeuraWall: Community $0 (1 node, self-hosted); Pro $149; Business $499; Enterprise $3,000; Dedicated $5-15k. 17% annual discount.
- Services $125/h; bundle discounts mentioned, undefined.
Inconsistency to resolve: Vigilo and NeuraWall use a different tier ladder and discount (17%) than the three 5-tier products (20%).

## 8. Cannot be cloned / out of scope
- Real Sentinel, CSPM, Gateway and NeuraWall engines: separate products, stubs only here.
- Marketplace and Labs content (unknown), enterprise SLA and support operations, dedicated deployments, professional services.
- Third-party data: Clerk, Stripe, Anthropic stay as vendors.

## 9. Size
- Screens: 27 (13 exist, 14 to build). Flows: 8. Entities: ~15 exist, ~6 new.
- Hard parts: (1) account-to-organization tenancy migration across every table, API dependency and test; (2) multi-product, multi-plan billing with per-product entitlements and usage metering; (3) cross-product API-key scoping and a single console API surface.
- Size: L (a quarter) for the full shell. M for shell skeleton + launcher + org + unified billing, with the other four products as stubs.
- Deploy: Docker Compose self-host stack and Caddy already exist (`docker-compose.self-host.yml`, `scripts/deploy.sh`).


## Scope decision, 2026-10-09
The build covers **the one product that exists, Vigilo, plus the platform around it** (accounts, organisations, roles, billing, usage, audit, console, marketing pages). Sentinel, CSPM, Gateway and NeuraWall are separate projects whose engines are not connected here; their pages, plans and pricing exist for reference and are labelled "Coming soon". The launcher cannot enable them (the API refuses until a slug is added to `AVAILABLE_PRODUCTS`). `features.csv` rows for them are `skip` with that reason. Revisit when an engine is connected to this Clerk app and this API.
