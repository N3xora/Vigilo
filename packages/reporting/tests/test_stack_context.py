from __future__ import annotations

from vigilo_core.models import Verdict
from vigilo_reporting.builder import build_report
from vigilo_reporting.context import stack_from_signals, stack_labels, why_here
from vigilo_reporting.guides import get_guide
from vigilo_reporting.remediation import template_remediation

from .test_builder import _GENERATED_AT, _finding, _manifest, _score


def test_stack_keys_are_sorted_and_deduplicated():
    assert stack_from_signals(["vercel"], ["next.js", "react"], ["supabase", "supabase"]) == [
        "next.js",
        "react",
        "supabase",
        "vercel",
    ]


def test_labels_skip_unknown_keys():
    assert stack_labels(["next.js", "mystery", "supabase"]) == ["Next.js", "Supabase"]


def test_database_findings_mention_the_backend_in_use():
    text = why_here("VG-DAT-002", "DAT", "title", ["supabase"])
    assert text is not None and "Supabase" in text
    assert "Firebase" in (why_here("VG-DAT-003", "DAT", "title", ["firebase"]) or "")


def test_bundle_key_findings_name_the_framework_prefix():
    title = "No AWS access key in client bundle"
    assert "NEXT_PUBLIC_" in (why_here("VG-CLI-001", "CLI", title, ["next.js"]) or "")
    assert "VITE_" in (why_here("VG-CLI-001", "CLI", title, ["vite"]) or "")


def test_no_sentence_when_the_stack_does_not_make_one_true():
    assert why_here("VG-DAT-002", "DAT", "title", []) is None
    assert why_here("VG-DAT-002", "DAT", "title", ["next.js"]) is None
    assert why_here("VG-CLI-001", "CLI", "No AWS access key in client bundle", ["astro"]) is None
    assert why_here("VG-TLS-001", "TLS", "title", ["vercel", "supabase"]) is None


def test_report_adds_why_here_only_to_failed_findings():
    manifests = {
        "VG-DAT-002": _manifest("VG-DAT-002", "DAT"),
        "VG-DAT-001": _manifest("VG-DAT-001", "DAT"),
    }
    findings = [_finding("VG-DAT-002", Verdict.FAILED), _finding("VG-DAT-001", Verdict.PASSED)]
    report = build_report(
        "https://example.com",
        _score(),
        findings,
        manifests,
        _GENERATED_AT,
        stack=["supabase", "vercel"],
    )
    by_id = {f.check_id: f for f in report.findings}
    assert by_id["VG-DAT-002"].why_here is not None
    assert by_id["VG-DAT-001"].why_here is None
    assert report.stack == ["Supabase", "Vercel"]


def test_report_without_a_stack_is_unchanged():
    manifests = {"VG-DAT-002": _manifest("VG-DAT-002", "DAT")}
    report = build_report(
        "https://example.com",
        _score(),
        [_finding("VG-DAT-002", Verdict.FAILED)],
        manifests,
        _GENERATED_AT,
    )
    assert report.stack == [] and report.findings[0].why_here is None


def test_supabase_rls_guide_replaces_the_one_line_template():
    guide = get_guide("VG-DAT-002")
    assert guide is not None
    finding = _finding("VG-DAT-002", Verdict.FAILED)
    prompt = template_remediation(finding, _manifest("VG-DAT-002", "DAT"))
    assert prompt.source == "template"
    assert prompt.remediation_steps == guide.steps and len(prompt.remediation_steps) == 5
    assert "enable row level security" in prompt.agent_prompt
    assert "service_role" in prompt.agent_prompt
    assert prompt.estimated_effort == "medium"
    assert prompt.agent_prompt.endswith("Context: summary")


def test_checks_without_a_guide_keep_the_manifest_text():
    prompt = template_remediation(_finding("VG-HDR-001", Verdict.FAILED), _manifest("VG-HDR-001"))
    assert prompt.remediation_steps == ["fix VG-HDR-001"]
