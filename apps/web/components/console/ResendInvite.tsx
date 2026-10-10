"use client";

import { useActionState } from "react";
import { resendInvite, type InviteState } from "../../app/console/members-actions";
import { Button } from "../ui";
import { InviteResult } from "./InviteResult";

const INITIAL: InviteState = { error: null, invitePath: null, email: null, emailStatus: null };

export function ResendInvite({ orgId, inviteId }: { orgId: string; inviteId: string }) {
  const [state, action, pending] = useActionState(resendInvite, INITIAL);
  return (
    <div className="space-y-2">
      <form action={action}>
        <input type="hidden" name="org_id" value={orgId} />
        <input type="hidden" name="invite_id" value={inviteId} />
        <Button type="submit" size="sm" variant="secondary" loading={pending}>
          Resend
        </Button>
      </form>
      {state.error ? (
        <p role="alert" className="text-xs text-nx-danger">
          {state.error}
        </p>
      ) : null}
      <InviteResult state={state} />
    </div>
  );
}
