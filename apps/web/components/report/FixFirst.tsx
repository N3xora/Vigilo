import type { ReportFindingResponse, Severity } from "../../lib/types";

const RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
  passed: 5,
};

const EFFORT_LABEL: Record<string, string> = {
  trivial: "trivial",
  small: "about 15 minutes",
  medium: "about an hour",
  large: "half a day or more",
};

const LIMIT = 3;

// The three open problems worth doing before anything else. Hidden when there
// are only a few open findings, because then the full list below is already
// the short list. Accepted risks never appear here.
export function pickFixFirst(findings: ReportFindingResponse[]): ReportFindingResponse[] {
  const open = findings.filter((f) => f.verdict === "failed" && !f.suppressed);
  if (open.length <= LIMIT) return [];
  // Array.prototype.sort is stable, so equal severities keep the report's order.
  return [...open].sort((a, b) => RANK[a.severity] - RANK[b.severity]).slice(0, LIMIT);
}

export function FixFirst({ findings }: { findings: ReportFindingResponse[] }) {
  const picks = pickFixFirst(findings);
  if (picks.length === 0) return null;

  return (
    <section aria-labelledby="fix-first" className="mb-6 rounded-lg border border-black/10 p-4 dark:border-white/10">
      <h2 id="fix-first" className="font-semibold">
        Fix these {picks.length} first
      </h2>
      <p className="mt-1 text-sm text-black/60 dark:text-white/60">
        Highest severity first. Everything else is listed below.
      </p>
      <ol className="mt-3 space-y-2 text-sm">
        {picks.map((f) => (
          <li key={f.fingerprint}>
            <a href={`#finding-${f.fingerprint}`} className="font-medium underline underline-offset-2">
              {f.title}
            </a>
            <span className="text-black/60 dark:text-white/60">
              {" "}
              · {f.severity}
              {f.remediation.estimated_effort
                ? ` · ${EFFORT_LABEL[f.remediation.estimated_effort] ?? f.remediation.estimated_effort}`
                : ""}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
