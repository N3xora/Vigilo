"use client";

import { useActionState } from "react";
import { acceptInvite, type AcceptState } from "../../app/console/members-actions";
import { Button } from "../ui";

const INITIAL: AcceptState = { error: null };

export function AcceptInviteForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState(acceptInvite, INITIAL);
  return (
    <form action={action} className="space-y-3">
      <input type="hidden" name="token" value={token} />
      {state.error ? (
        <p role="alert" className="text-sm text-nx-danger">
          {state.error}
        </p>
      ) : null}
      <Button type="submit" loading={pending}>
        Accept invitation
      </Button>
    </form>
  );
}
