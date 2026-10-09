from __future__ import annotations

from vigilo_core.models import CheckManifest, Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_reporting.pr_comment import build_pr_comment_markdown


def _manifest(check_id: str, severity: Severity = Severity.HIGH) -> CheckManifest:
    return CheckManifest(
        check_id=check_id,
        category="HDR",
        title=f"title for {check_id}",
        description="desc",
        severity_default=severity,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        remediation_template=f"fix {check_id}",
        introduced_in="0.1",
    )


def _finding(check_id: str, verdict: Verdict, severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        check_id=check_id,
        verdict=verdict,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        title=f"title for {check_id}",
        summary=f"summary for {check_id}",
        fingerprint=f"fp-{check_id}",
    )


def _score(value: float = 72.0) -> Score:
    return Score(value=value, grade="C", registry_version="1.0")


def test_comment_starts_with_the_marker_used_for_upsert():
    markdown = build_pr_comment_markdown("https://example.com", [], {}, _score())
    assert markdown.startswith("<!-- vigilo-scan-comment -->")


def test_comment_reports_no_failed_checks_when_there_are_none():
    findings = [_finding("VG-HDR-001", Verdict.PASSED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    markdown = build_pr_comment_markdown("https://example.com", findings, manifests, _score())

    assert "No failed checks." in markdown


def test_only_failed_findings_get_a_table_row():
    findings = [
        _finding("VG-HDR-001", Verdict.PASSED),
        _finding("VG-HDR-002", Verdict.NOT_APPLICABLE),
        _finding("VG-HDR-003", Verdict.FAILED),
    ]
    manifests = {f.check_id: _manifest(f.check_id) for f in findings}

    markdown = build_pr_comment_markdown("https://example.com", findings, manifests, _score())

    assert "VG-HDR-001" not in markdown
    assert "VG-HDR-002" not in markdown
    assert "title for VG-HDR-003" in markdown
    assert "1 failed check(s)" in markdown


def test_failed_findings_are_sorted_most_severe_first():
    findings = [
        _finding("VG-AA-002", Verdict.FAILED, severity=Severity.LOW),
        _finding("VG-AA-001", Verdict.FAILED, severity=Severity.CRITICAL),
    ]
    manifests = {f.check_id: _manifest(f.check_id) for f in findings}

    markdown = build_pr_comment_markdown("https://example.com", findings, manifests, _score())

    assert markdown.index("title for VG-AA-001") < markdown.index("title for VG-AA-002")


def test_remediation_template_is_included_in_a_collapsed_details_block():
    findings = [_finding("VG-HDR-001", Verdict.FAILED)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    markdown = build_pr_comment_markdown("https://example.com", findings, manifests, _score())

    assert "<details><summary>Fix</summary>" in markdown
    assert "fix VG-HDR-001" in markdown


def test_inconclusive_findings_are_counted_but_not_tabulated():
    findings = [_finding("VG-HDR-001", Verdict.INCONCLUSIVE)]
    manifests = {"VG-HDR-001": _manifest("VG-HDR-001")}

    markdown = build_pr_comment_markdown("https://example.com", findings, manifests, _score())

    assert "No failed checks." in markdown
    assert "1 check(s) inconclusive" in markdown


def test_score_and_grade_are_shown():
    markdown = build_pr_comment_markdown(
        "https://example.com", [], {}, Score(value=88.5, grade="B", registry_version="1.0")
    )

    assert "88.5" in markdown
    assert "(B)" in markdown
