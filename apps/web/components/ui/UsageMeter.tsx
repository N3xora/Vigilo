import { cx } from "./cx";

export function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  const unlimited = limit === null;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  const hot = !unlimited && pct >= 90;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-sm">
        <span className="text-nx-text">{label}</span>
        <span className="text-nx-text-muted">
          {used.toLocaleString("en-US")} / {unlimited ? "unlimited" : limit.toLocaleString("en-US")}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={unlimited ? undefined : limit}
        aria-valuenow={used}
        className="h-2 overflow-hidden rounded-full bg-nx-surface ring-1 ring-nx-border"
      >
        <div
          className={cx("h-full", hot ? "bg-nx-danger" : "bg-nx-accent")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
