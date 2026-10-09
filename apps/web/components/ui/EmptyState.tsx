import type { ReactNode } from "react";

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-nx-lg border border-dashed border-nx-border bg-nx-surface px-6 py-12 text-center">
      <h3 className="text-lg font-semibold text-nx-text">{title}</h3>
      <p className="max-w-md text-sm text-nx-text-muted">{body}</p>
      {action}
    </div>
  );
}
