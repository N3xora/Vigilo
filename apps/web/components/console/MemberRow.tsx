import { changeRole, removeMember } from "../../app/console/members-actions";
import { TransferOwnershipForm } from "./TransferOwnershipForm";
import type { Member } from "../../lib/nexora/data";
import { Badge, Button } from "../ui";

const ASSIGNABLE = ["viewer", "member", "admin"] as const;

// Server-rendered, no client JS: a role select with its own Save button, and a
// two-step remove (open "Remove", then confirm) built on <details>.
export function MemberRow({
  member,
  orgId,
  isYou,
  canManage,
  transfer,
}: {
  member: Member;
  orgId: string;
  isYou: boolean;
  canManage: boolean;
  // Set only when the viewer is the owner of a team organisation.
  transfer?: { orgName: string; orgSlug: string };
}) {
  const locked = member.role === "owner";
  return (
    <tr className="border-b border-nx-border align-top last:border-0">
      <td className="break-all px-4 py-3 text-nx-text">
        {member.email}
        {isYou ? <span className="ml-2 text-xs text-nx-text-muted">(you)</span> : null}
      </td>
      <td className="px-4 py-3">
        {canManage && !locked ? (
          <form action={changeRole} className="flex items-center gap-2">
            <input type="hidden" name="org_id" value={orgId} />
            <input type="hidden" name="account_id" value={member.accountId} />
            <label htmlFor={`role-${member.accountId}`} className="sr-only">
              Role for {member.email}
            </label>
            <select
              id={`role-${member.accountId}`}
              name="role"
              defaultValue={member.role}
              className="h-8 rounded-nx-md border border-nx-border-input bg-nx-bg px-2 text-sm text-nx-text focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-nx-accent"
            >
              {ASSIGNABLE.map((r) => (
                <option key={r} value={r}>
                  {r[0].toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" variant="secondary">
              Save
            </Button>
          </form>
        ) : (
          <Badge>{member.role}</Badge>
        )}
      </td>
      <td className="space-y-2 px-4 py-3">
        {transfer && !locked && !isYou ? (
          <details>
            <summary className="cursor-pointer text-sm text-nx-text underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-nx-accent">
              Make owner
            </summary>
            <TransferOwnershipForm
              orgId={orgId}
              orgName={transfer.orgName}
              orgSlug={transfer.orgSlug}
              accountId={member.accountId}
              email={member.email}
            />
          </details>
        ) : null}
        {canManage && !locked && !isYou ? (
          <details>
            <summary className="cursor-pointer text-sm text-nx-danger underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-nx-accent">
              Remove
            </summary>
            <form action={removeMember} className="mt-2 space-y-2">
              <input type="hidden" name="org_id" value={orgId} />
              <input type="hidden" name="account_id" value={member.accountId} />
              <p className="text-xs text-nx-text-muted">
                {member.email} loses access to this organisation at once.
              </p>
              <Button type="submit" size="sm" variant="danger">
                Remove {member.email}
              </Button>
            </form>
          </details>
        ) : null}
      </td>
    </tr>
  );
}
