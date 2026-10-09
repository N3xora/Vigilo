"use client";

import { useActionState } from "react";
import { deleteMyAccount, type DeleteAccountState } from "../../app/console/members-actions";
import { Button, Input } from "../ui";

const INITIAL: DeleteAccountState = { error: null, blockers: [] };

export function DeleteAccountForm({ email }: { email: string }) {
  const [state, action, pending] = useActionState(deleteMyAccount, INITIAL);
  return (
    <form action={action} className="max-w-md space-y-3">
      <Input
        label={`Type ${email} to confirm`}
        name="confirm_email"
        type="email"
        autoComplete="off"
        required
      />
      {state.error ? (
        <div role="alert" className="space-y-1 text-sm text-nx-danger">
          <p>{state.error}</p>
          {state.blockers.length > 0 ? (
            <ul className="list-disc pl-5">
              {state.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <Button type="submit" variant="danger" loading={pending}>
        Delete my account permanently
      </Button>
    </form>
  );
}
