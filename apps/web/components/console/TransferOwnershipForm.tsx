"use client";

import { useActionState } from "react";
import { transferOwnership, type TransferState } from "../../app/console/members-actions";
import { Button, Input } from "../ui";

const INITIAL: TransferState = { error: null };

export function TransferOwnershipForm({
  orgId,
  orgName,
  orgSlug,
  accountId,
  email,
}: {
  orgId: string;
  orgName: string;
  orgSlug: string;
  accountId: string;
  email: string;
}) {
  const [state, action, pending] = useActionState(transferOwnership, INITIAL);
  return (
    <form action={action} className="mt-2 max-w-xs space-y-2">
      <input type="hidden" name="org_id" value={orgId} />
      <input type="hidden" name="account_id" value={accountId} />
      <p className="text-xs text-nx-text-muted">
        {email} becomes the owner of {orgName}: billing, members and deletion. You stay an admin.
        Only they can hand it back.
      </p>
      <Input label={`Type ${orgSlug} to confirm`} name="confirm_slug" autoComplete="off" required />
      {state.error ? (
        <p role="alert" className="text-xs text-nx-danger">
          {state.error}
        </p>
      ) : null}
      <Button type="submit" size="sm" variant="danger" loading={pending}>
        Hand over to {email}
      </Button>
    </form>
  );
}
