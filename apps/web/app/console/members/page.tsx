import { currentAccountId, getActiveOrg, listMembers, listPendingInvites } from "../../../lib/nexora/data";
import { InviteForm } from "../../../components/console/InviteForm";
import { MemberRow } from "../../../components/console/MemberRow";
import { ResendInvite } from "../../../components/console/ResendInvite";
import { Badge, Button, Card } from "../../../components/ui";
import { leaveOrg, revokeInvite } from "../members-actions";

export const metadata = { title: "Members" };

const ROLE_HELP: Array<[string, string]> = [
  ["Viewer", "reads reports, targets and usage"],
  ["Member", "adds and verifies targets, runs monitors, accepts risks"],
  ["Admin", "also manages API keys, branding, billing, share links and members"],
  ["Owner", "one per organisation; can hand it to another member, and cannot be removed or demoted"],
];

export default async function MembersPage() {
  const org = await getActiveOrg();
  const canManage = org.role === "owner" || org.role === "admin";
  const [members, meId, invites] = await Promise.all([
    listMembers(org.id),
    currentAccountId(),
    canManage ? listPendingInvites(org.id) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-[28px] font-bold leading-[34px] text-nx-text">Members</h1>
        <p className="mt-1 text-sm text-nx-text-muted">
          {org.isPersonal
            ? "This is your personal workspace. You can invite people into it, or create an organisation for a team."
            : `People with access to ${org.name}.`}
        </p>
      </div>

      <Card className="p-0">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Organisation members</caption>
          <thead className="border-b border-nx-border text-nx-text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Email</th>
              <th scope="col" className="px-4 py-3 font-medium">Role</th>
              <th scope="col" className="px-4 py-3 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <MemberRow
                key={m.accountId}
                member={m}
                orgId={org.id}
                isYou={m.accountId === meId}
                canManage={canManage}
                transfer={
                  org.role === "owner" && !org.isPersonal
                    ? { orgName: org.name, orgSlug: org.slug }
                    : undefined
                }
              />
            ))}
          </tbody>
        </table>
      </Card>

      {canManage ? (
        <section aria-labelledby="invite-heading" className="space-y-3">
          <h2 id="invite-heading" className="text-xl font-semibold text-nx-text">
            Invite someone
          </h2>
          <InviteForm orgId={org.id} />
        </section>
      ) : (
        <p className="text-sm text-nx-text-muted">Only owners and admins can invite people or change roles.</p>
      )}

      {canManage && invites.length > 0 ? (
        <section aria-labelledby="pending-heading" className="space-y-3">
          <h2 id="pending-heading" className="text-xl font-semibold text-nx-text">
            Waiting to join
          </h2>
          <ul className="divide-y divide-nx-border rounded-nx-lg border border-nx-border">
            {invites.map((i) => {
              return (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                  <span className="break-all text-nx-text">
                    {i.email} <Badge>{i.role}</Badge>
                    {i.expired ? <span className="ml-2 text-xs text-nx-danger">expired</span> : null}
                  </span>
                  <div className="flex flex-wrap items-start gap-2">
                    <ResendInvite orgId={org.id} inviteId={i.id} />
                    <form action={revokeInvite}>
                      <input type="hidden" name="org_id" value={org.id} />
                      <input type="hidden" name="invite_id" value={i.id} />
                      <Button type="submit" size="sm" variant="ghost">
                        Withdraw
                      </Button>
                    </form>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="roles-heading" className="space-y-2">
        <h2 id="roles-heading" className="text-sm font-semibold text-nx-text">What each role can do</h2>
        <dl className="space-y-1 text-sm">
          {ROLE_HELP.map(([role, what]) => (
            <div key={role} className="flex gap-2">
              <dt className="w-16 shrink-0 font-medium text-nx-text">{role}</dt>
              <dd className="text-nx-text-muted">{what}</dd>
            </div>
          ))}
        </dl>
      </section>

      {!org.isPersonal && org.role !== "owner" ? (
        <section aria-labelledby="leave-heading" className="space-y-2">
          <h2 id="leave-heading" className="text-sm font-semibold text-nx-text">Leave this organisation</h2>
          <details>
            <summary className="cursor-pointer text-sm text-nx-danger underline underline-offset-2">
              Leave {org.name}
            </summary>
            <form action={leaveOrg} className="mt-2 space-y-2">
              <input type="hidden" name="org_id" value={org.id} />
              <input type="hidden" name="account_id" value={meId} />
              <p className="text-xs text-nx-text-muted">
                You lose access to its targets, reports and settings. An admin can invite you again.
              </p>
              <Button type="submit" size="sm" variant="danger">
                Leave {org.name}
              </Button>
            </form>
          </details>
        </section>
      ) : null}
    </div>
  );
}
