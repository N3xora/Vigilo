import { useId, type InputHTMLAttributes } from "react";
import { cx } from "./cx";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function Input({ label, hint, error, className, id, ...rest }: InputProps) {
  const auto = useId();
  const inputId = id ?? auto;
  const noteId = `${inputId}-note`;
  const note = error ?? hint;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-sm font-medium text-nx-text">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        {...rest}
        className={cx(
          "h-10 rounded-nx-md border bg-nx-bg px-3 text-sm text-nx-text",
          "placeholder:text-nx-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-nx-accent",
          "disabled:cursor-not-allowed disabled:opacity-50",
          error ? "border-nx-danger" : "border-nx-border-input",
          className,
        )}
      />
      {note && (
        <p id={noteId} className={cx("text-xs", error ? "text-nx-danger" : "text-nx-text-muted")}>
          {note}
        </p>
      )}
    </div>
  );
}
