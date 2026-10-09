import type { ReactNode } from "react";
import { cx } from "./cx";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger";

const TONE: Record<Tone, string> = {
  neutral: "bg-nx-surface text-nx-text-muted border border-nx-border",
  accent: "bg-nx-accent-soft text-nx-on-accent-soft",
  success: "bg-nx-surface text-nx-success border border-nx-success",
  warning: "bg-nx-surface text-nx-warning border border-nx-warning",
  danger: "bg-nx-surface text-nx-danger border border-nx-danger",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        TONE[tone],
      )}
    >
      {children}
    </span>
  );
}
