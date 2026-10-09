import type { HTMLAttributes } from "react";
import { cx } from "./cx";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cx(
        "rounded-nx-lg border border-nx-border bg-nx-bg p-6 shadow-nx-card",
        className,
      )}
    />
  );
}
