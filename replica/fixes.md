# Fixes and positioning (2026-10-07)

## Read this first: the evidence is thin
- The "original" here is your own platform, and it has no public reviews yet (all products are in beta). So this research is about the category it competes in, not about Nexora or Vigilo.
- Sample: **8 comments, 1 source (Hacker News)**, 0 star ratings. The tool's own rule: under 30 reviews supports a direction, not a ranking. Every theme below is marked thin (under 3 reviews or a single source, here both).
- I did not reach Reddit (its API needs your credentials and terms), G2/Capterra/Trustpilot, app stores, or any feature-request board. No quote or count in this file was invented; each is linked in `reviews.csv` and I checked all 8 against the live HN text.
- 2 of the 8 comments are by people promoting their own scanner (47138255, 47901990). They are evidence that competitors exist, not independent users.

## 1. What they hate (all thin)
1. **False positives and noise**: 4 comments, 1 source. "This is greatly exacerbated by the fact that Snyk - like all package scanners - primarily flags false positives." https://news.ycombinator.com/item?id=32174100 / "They're kind of useless really." https://news.ycombinator.com/item?id=49782578 (These are about Snyk and dependency scanners, a different job from scanning a live URL.)
2. **Findings with no context about the app**: 3 comments. "\"~25 security issues per codebase\" means nothing without a grounding in the codebase's actual security model" https://news.ycombinator.com/item?id=48605489
3. **AI-generated apps ship insecure by default**: 3 comments. "The RLS problem is systemic" https://news.ycombinator.com/item?id=47901990 / "And most vibe coders don't have a security background, so they don't know what to look for." https://news.ycombinator.com/item?id=47138255
4. Price: one comment, not a trend. "It's absurd that companies are charging $100/mo just to run your dependency list against another public list of vulnerabilities." (2017) https://news.ycombinator.com/item?id=15717825. Goes to `/replica-launch`, not a fix.

## 2. What is missing
Nothing matched a "wish/please add" pattern. No requests found, so none are claimed.

## 3. What is unsolved
- Non-technical builders of generated apps who cannot read a security report (item 3 above; also the premise of Vigilo's paste-ready prompts). Thin, and already contested by several small scanners named in the same threads.
- Platform-level claim ("one account for security + AI governance"): **zero evidence** in this sample for or against.

## 4. Fix plan (cheap, evidence-aligned, all unproven demand)
| # | change | size | skill | evidence |
| --- | --- | --- | --- | --- |
| 1 | "Fix these first": top 3 findings pinned above the full list | S | replica-build | noise theme, 4 comments |
| 2 | Stack-aware "why this matters for your app" line on each finding, using the existing fingerprinting | M | replica-build | context theme, 3 comments |
| 3 | Any org member (not only the owner) can accept a risk with a reason; visible in the report | S | replica-backend | https://news.ycombinator.com/item?id=32174100 describes devs needing tickets to ignore findings |
| 4 | Supabase RLS walkthrough prompt for the flagship exposed-table check | S | replica-build | vibe-defaults theme |
| 5 | Optional "what is this app?" questions that tune severity | L | later | context theme; speculative, do last |
Already true and worth keeping loud: every finding carries a recorded request/response (no "possible" findings), inconclusive checks are shown separately, and suppressions exist. Added to `features.csv` as rows with `original = no`.

## 5. Positioning options
A. For **people shipping apps built with AI tools** who are tired of scanners that bury them in alerts, Vigilo reports only what it can prove with a recorded request and gives the prompt that fixes it. Evidence: false positives, 4 comments, 1 source (thin).
B. For **small engineering teams with no security function**, one Nexora account covers scanning, logs and cloud config. Evidence: none in this sample. Based only on onenexora.com's own claims.
C. For **Supabase/Lovable/Bolt builders**, Vigilo checks the mistakes those tools repeat. Evidence: vibe defaults, 3 comments (thin); crowded: at least four other small scanners appear in the same threads.

**Recommend A** as the Vigilo hero inside Nexora; it is the only one grounded in complaints and it matches what the product already does. Treat B as a hypothesis to test with real users, not a claim. Do not name Snyk or any competitor in the app name, listings or ads; a comparison page is a question for a lawyer.

## Next
Collect 100+ reviews before betting the roadmap: Vigilo's own early users (ask the first 20 free-tier users why they left or stayed), Reddit threads read in the browser, and G2/Capterra pages for the three nearest competitors.
