# GitHub Action

## Purpose

`.github/actions/scan` — the CI distribution channel: drop a scan of your
deployed preview/staging URL into a workflow, get results in GitHub's
Security tab, optionally fail the build. Runs the open-source `vigilo`
CLI standalone (`apps/cli`) — no account, no API key, no signup. This is
deliberately separate from the key-authenticated public API's own
`GET /public/v1/scans/{id}/report.sarif` (`docs/api.md`), which exists for
customers who already have persisted, monitored scans and want CI tied
into those specifically rather than a fresh standalone scan per run.

## Usage

```yaml
# .github/workflows/security-scan.yml
name: Security scan
on: [pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # ... your own steps to build and deploy a preview, producing a URL ...

      - name: Vigilo security scan
        uses: <org>/vigilo/.github/actions/scan@main
        with:
          target-url: ${{ steps.deploy.outputs.preview-url }}
          fail-on: high        # optional — omit to never fail the build
          post-comment: true   # optional — also post a PR comment summary
```

To post a PR comment, also grant the job comment permission:

```yaml
jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write   # required only when post-comment: true
    steps:
      # ...
```

## Inputs

| Input | Required | Notes |
|---|---|---|
| `target-url` | Yes | The deployed URL to scan. Must already be live and reachable from GitHub's runners when the step executes. |
| `fail-on` | No | `critical`, `high`, `medium`, or `low`. The job fails if any failed finding is at or above this severity. Omit to always pass regardless of findings — the SARIF upload still happens either way. |
| `post-comment` | No | `true` to post (or update in place) a single PR comment summarizing the findings, alongside the SARIF upload. Only has effect on a `pull_request` event; needs `pull-requests: write` on the calling job. Default `false`. |

## PR comments

When `post-comment: true` and the workflow run is triggered by a
`pull_request` event, the action renders the same scan's JSON report
(`apps/cli`'s `--json-out`, never a second scan — see "What it does" below)
as markdown via `vigilo render-pr-comment` and posts it to the PR. A hidden
marker comment (`<!-- vigilo-scan-comment -->`) lets it find and update its
own prior comment on later pushes instead of piling up a new one each time
— see `packages/reporting/src/vigilo_reporting/pr_comment.py`'s module
docstring. Only `FAILED` findings are tabulated, with each one's
`remediation_template` in a collapsed details block; `INCONCLUSIVE`
findings are counted but not tabulated — the same reportable/suppressed
split `build_sarif_report` already applies, just rendered as markdown
instead of SARIF.

## What it does

One live scan produces the SARIF file, the pass/fail decision, and (when
`post-comment: true`) the JSON report the PR comment is rendered from —
`apps/cli`'s `vigilo scan <url> --sarif --fail-on <level> --json-out
<path>` reads its own single result for all three, never two separate
scans of the same target (a second scan could legitimately return
different results, since the target is live). The SARIF is uploaded to
GitHub Code Scanning via `github/codeql-action/upload-sarif@v3` *before*
the action enforces `fail-on` — findings are always visible in the
Security tab even on a failed build, never hidden by early job
termination.

Only `FAILED`/`INCONCLUSIVE` findings become SARIF results (never
`PASSED`/`NOT_APPLICABLE`) — see
`packages/reporting/src/vigilo_reporting/sarif.py`'s module docstring for
the full SARIF-shape reasoning, including the honest adaptation this makes
for live-URL findings having no source file or line number (SARIF's
location model assumes source code, not a deployed site — the scanned
origin is used as the location instead of pointing at an unrelated real
file).

## Known limitation

GitHub Code Scanning's own SARIF conventions were built around source-code
(SAST) tools. This action's output validates against the real SARIF 2.1.0
schema and lists findings in the Security tab, but the inline
"jump to code" annotation experience doesn't make sense for a live-URL
finding the way it does for a source-code one — there is no documented
precedent for DAST tools to follow here (checked GitHub's own SARIF docs
and the OWASP ZAP GitHub Action; neither addresses this). Confirmed
against a real GitHub Actions run producing valid, schema-conformant SARIF
(`docs/build-roadmap.md`'s entry for this work); the alert-rendering
experience in a real repo's Security tab is the one thing to watch on
first real-world use.
