"use client";

import { useActionState } from "react";
import { createOrg, type CreateOrgState } from "../../app/console/actions";
import { Button, Input } from "../ui";

const INITIAL: CreateOrgState = { error: null };

export function NewOrgForm() {
  const [state, action, pending] = useActionState(createOrg, INITIAL);
  return (
    <form action={action} className="grid max-w-md gap-4">
      <Input label="Name" name="name" required maxLength={200} placeholder="Acme Platform Team" />
      <Input
        label="Address"
        name="slug"
        required
        minLength={2}
        maxLength={48}
        pattern="[a-z0-9\-]{2,48}"
        hint="Lowercase letters, numbers and dashes. Used in links, cannot be changed later."
        placeholder="acme-platform"
      />
      {state.error && (
        <p role="alert" className="text-sm text-nx-danger">
          {state.error}
        </p>
      )}
      <div>
        <Button type="submit" loading={pending}>
          Create organisation
        </Button>
      </div>
    </form>
  );
}
