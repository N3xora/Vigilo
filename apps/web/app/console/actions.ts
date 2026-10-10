"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { api, ApiError } from "../../lib/api";
import { ACTIVE_ORG_COOKIE, listMyOrgs, sessionToken } from "../../lib/nexora/data";

async function remember(orgId: string) {
  (await cookies()).set(ACTIVE_ORG_COOKIE, orgId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
}

export async function switchOrg(formData: FormData): Promise<void> {
  const orgId = String(formData.get("org_id") ?? "");
  // Only an org the caller belongs to can become active.
  const orgs = await listMyOrgs();
  if (orgs.some((o) => o.id === orgId)) {
    await remember(orgId);
    revalidatePath("/console", "layout");
  }
  redirect(await returnPath());
}

// Back to the console or dashboard page the switch was made from; the Referer
// is only used for its path, and only if that path is one of ours.
async function returnPath(): Promise<string> {
  const referer = (await headers()).get("referer");
  try {
    const path = referer ? new URL(referer).pathname : "";
    if (path.startsWith("/console") || path.startsWith("/dashboard")) return path;
  } catch {
    // malformed Referer: fall through
  }
  return "/console";
}

export interface CreateOrgState {
  error: string | null;
}

export async function createOrg(_prev: CreateOrgState, formData: FormData): Promise<CreateOrgState> {
  const name = String(formData.get("name") ?? "").trim();
  const slug = String(formData.get("slug") ?? "").trim().toLowerCase();
  if (!name) return { error: "Give the organisation a name." };
  try {
    const org = await api.createOrg({ name, slug }, await sessionToken());
    await remember(org.org_id);
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 409) return { error: "That address is taken. Try another." };
      if (err.status === 422) return { error: "Use 2-48 lowercase letters, numbers or dashes for the address." };
    }
    return { error: "Could not create the organisation. Try again." };
  }
  revalidatePath("/console", "layout");
  redirect("/console");
}

export async function enableProduct(formData: FormData): Promise<void> {
  const slug = String(formData.get("product") ?? "");
  const orgs = await listMyOrgs();
  const wanted = String(formData.get("org_id") ?? "");
  const org = orgs.find((o) => o.id === wanted);
  // The API enforces the admin role; this just avoids a pointless call.
  if (org && (org.role === "owner" || org.role === "admin")) {
    await api.enableOrgProduct(org.id, slug, await sessionToken());
    revalidatePath("/console");
  }
}
