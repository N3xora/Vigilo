"use client";

import { useActionState } from "react";
import { inviteMember, type InviteState } from "../../app/console/members-actions";
import { Button, Input } from "../ui";
import { InviteResult } from "./InviteResult";

const INITIAL: InviteState = { error: null, invitePath: null, email: null, emailStatus: null };

export function InviteForm({ orgId }: { orgId: string }) {
  const [state, action, pending] = useActionState(inviteMember, INITIAL);
  return (
    <div className="space-y-4">
      <form action={action} className="grid max-w-xl gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        <input type="hidden" name="org_id" value={orgId} />
        <Input label="Email address" name="email" type="email" required placeholder="teammate@company.com" />
        <div className="flex flex-col gap-1">
          <label htmlFor="invite-role" className="text-sm font-medium text-nx-text">
            Role
          </label>
          <select
            id="invite-role"
            name="role"
            defaultValue="member"
            className="h-10 rounded-nx-md border border-nx-border-input bg-nx-bg px-2 text-sm text-nx-text focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-nx-accent"
          >
            <option value="viewer">Viewer</option>
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <Button type="submit" loading={pending}>
          Create invitation
        </Button>
      </form>

      {state.error ? (
        <p role="alert" className="text-sm text-nx-danger">
          {state.error}
        </p>
      ) : null}

      <InviteResult state={state} />
    </div>
  );
}
