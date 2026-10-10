"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { api, ApiError } from "../../lib/api";
import { ACTIVE_ORG_COOKIE, sessionToken } from "../../lib/nexora/data";

export interface InviteState {
  error: string | null;
  invitePath: string | null;
  email: string | null;
  emailStatus: "sent" | "not_configured" | "rate_limited" | "failed" | null;
}

const NO_INVITE: InviteState = { error: null, invitePath: null, email: null, emailStatus: null };

function message(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return "That person is already a member.";
    if (err.status === 403) return "Only owners and admins can do that.";
    if (err.status === 422) return "Check the email address and role.";
  }
  return fallback;
}

export async function inviteMember(_prev: InviteState, formData: FormData): Promise<InviteState> {
  const orgId = String(formData.get("org_id") ?? "");
  const email = String(formData.get("email") ?? "").trim();
  const role = String(formData.get("role") ?? "member");
  if (!email) return { ...NO_INVITE, error: "Enter an email address." };
  try {
    const invite = await api.createOrgInvite(orgId, { email, role }, await sessionToken());
    revalidatePath("/console/members");
    // The link is only ever shown here, once: the API stores a hash, not the token.
    return {
      error: null,
      invitePath: `/invite/${invite.token}`,
      email: invite.email,
      emailStatus: invite.email_status,
    };
  } catch (err) {
    return { ...NO_INVITE, error: message(err, "Could not create the invitation.") };
  }
}

// The forms below are plain server-action forms. When the API refuses (a role
// changed under you, an invite already used), the page simply re-renders with
// what is true now.

export async function changeRole(formData: FormData): Promise<void> {
  try {
    await api.changeMemberRole(
      String(formData.get("org_id")),
      String(formData.get("account_id")),
      String(formData.get("role")),
      await sessionToken(),
    );
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
  }
  revalidatePath("/console/members");
}

export async function removeMember(formData: FormData): Promise<void> {
  try {
    await api.removeOrgMember(
      String(formData.get("org_id")),
      String(formData.get("account_id")),
      await sessionToken(),
    );
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
  }
  revalidatePath("/console/members");
}

export async function leaveOrg(formData: FormData): Promise<void> {
  const orgId = String(formData.get("org_id"));
  const accountId = String(formData.get("account_id"));
  try {
    await api.removeOrgMember(orgId, accountId, await sessionToken());
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    redirect("/console/members");
  }
  const store = await cookies();
  if (store.get(ACTIVE_ORG_COOKIE)?.value === orgId) store.delete(ACTIVE_ORG_COOKIE);
  revalidatePath("/console", "layout");
  redirect("/console");
}

// Same result shape as inviteMember: a resend makes a new link (the old one stops
// working) and the page shows it once, exactly like a new invitation.
export async function resendInvite(
  _prev: InviteState,
  formData: FormData,
): Promise<InviteState> {
  try {
    const invite = await api.resendOrgInvite(
      String(formData.get("org_id")),
      String(formData.get("invite_id")),
      await sessionToken(),
    );
    revalidatePath("/console/members");
    return {
      error: null,
      invitePath: `/invite/${invite.token}`,
      email: invite.email,
      emailStatus: invite.email_status,
    };
  } catch (err) {
    return { ...NO_INVITE, error: message(err, "Could not resend the invitation.") };
  }
}

export async function revokeInvite(formData: FormData): Promise<void> {
  try {
    await api.revokeOrgInvite(
      String(formData.get("org_id")),
      String(formData.get("invite_id")),
      await sessionToken(),
    );
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
  }
  revalidatePath("/console/members");
}

export interface AcceptState {
  error: string | null;
}

export async function acceptInvite(_prev: AcceptState, formData: FormData): Promise<AcceptState> {
  const inviteToken = String(formData.get("token") ?? "");
  let orgId: string;
  try {
    orgId = (await api.acceptOrgInvite(inviteToken, await sessionToken())).org_id;
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 410) return { error: "This invitation has expired. Ask for a new one." };
      if (err.status === 409) return { error: "You are already a member of this organisation." };
      if (err.status === 404) {
        return {
          error:
            "This invitation is not valid for this account. It may have been used or withdrawn, or it was sent to a different email address.",
        };
      }
    }
    return { error: "Could not accept the invitation. Try again." };
  }
  (await cookies()).set(ACTIVE_ORG_COOKIE, orgId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  revalidatePath("/console", "layout");
  redirect("/console");
}

export interface DeleteAccountState {
  error: string | null;
  blockers: string[];
}

export async function deleteMyAccount(
  _prev: DeleteAccountState,
  formData: FormData,
): Promise<DeleteAccountState> {
  const email = String(formData.get("confirm_email") ?? "").trim();
  if (!email) return { error: "Type your email address to confirm.", blockers: [] };
  try {
    await api.deleteAccount(email, await sessionToken());
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 422) return { error: "That is not the email address on this account.", blockers: [] };
      if (err.status === 409) {
        const detail = (err.body as { detail?: { blockers?: string[] } } | null)?.detail;
        return {
          error: "Finish these first, then try again.",
          blockers: Array.isArray(detail?.blockers) ? detail.blockers : [],
        };
      }
    }
    return { error: "Could not delete the account. Nothing was changed.", blockers: [] };
  }
  (await cookies()).delete(ACTIVE_ORG_COOKIE);
  redirect("/account-deleted");
}

export interface TransferState {
  error: string | null;
}

export async function transferOwnership(
  _prev: TransferState,
  formData: FormData,
): Promise<TransferState> {
  const orgId = String(formData.get("org_id") ?? "");
  const accountId = String(formData.get("account_id") ?? "");
  const slug = String(formData.get("confirm_slug") ?? "").trim();
  if (!slug) return { error: "Type the organisation's address to confirm." };
  try {
    await api.transferOrgOwnership(
      orgId,
      { new_owner_account_id: accountId, confirm_slug: slug },
      await sessionToken(),
    );
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 422) return { error: "That is not this organisation's address." };
      if (err.status === 403) return { error: "Only the current owner can hand the organisation over." };
      if (err.status === 404) return { error: "That person is no longer a member." };
      if (err.status === 409) return { error: "A personal workspace cannot be handed over." };
    }
    return { error: "Could not hand the organisation over. Nothing was changed." };
  }
  revalidatePath("/console", "layout");
  return { error: null };
}
