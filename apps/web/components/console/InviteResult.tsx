"use client";

import { useState } from "react";
import type { InviteState } from "../../app/console/members-actions";
import { Button } from "../ui";

const HEADLINE: Record<NonNullable<InviteState["emailStatus"]>, (email: string) => string> = {
  sent: (email) => `We emailed ${email}. You can also share the link yourself.`,
  not_configured: (email) =>
    `Invitation for ${email} created, but email sending is not set up here. Send them this link yourself.`,
  rate_limited: (email) =>
    `Invitation for ${email} created, but we did not email it because too many invitations went out recently. Send them this link yourself.`,
  failed: (email) =>
    `Invitation for ${email} created, but the email could not be sent. Send them this link yourself.`,
};

// Shows the one-time link after an invite or a resend, and what happened to the email.
export function InviteResult({ state }: { state: InviteState }) {
  const [copied, setCopied] = useState(false);
  if (!state.invitePath || !state.email || !state.emailStatus) return null;
  const link =
    typeof window !== "undefined" ? `${window.location.origin}${state.invitePath}` : state.invitePath;

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div role="status" className="max-w-xl space-y-2 rounded-nx-lg border border-nx-border bg-nx-surface p-4">
      <p className="text-sm text-nx-text">{HEADLINE[state.emailStatus](state.email)}</p>
      <div className="flex items-center gap-2">
        <input
          readOnly
          aria-label="Invitation link"
          value={link}
          onFocus={(e) => e.currentTarget.select()}
          className="h-9 min-w-0 flex-1 rounded-nx-md border border-nx-border-input bg-nx-bg px-2 text-xs text-nx-text"
        />
        <Button type="button" size="sm" variant="secondary" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <p className="text-xs text-nx-text-muted">
        It works once, only for that email address, and expires in 7 days. You will not see this link
        again; resend the invitation for a new one.
      </p>
    </div>
  );
}
