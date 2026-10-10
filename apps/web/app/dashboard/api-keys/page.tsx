import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../../lib/api";
import { getActiveOrg } from "../../../lib/nexora/data";
import { ApiKeysManager } from "../../../components/dashboard/ApiKeysManager";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function DashboardApiKeysPage() {
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  const org = await getActiveOrg();
  if (org.role !== "owner" && org.role !== "admin") {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">API keys</h1>
        <p className="text-sm text-black/60 dark:text-white/60">
          Only owners and admins of {org.name} can manage its API keys.
        </p>
      </div>
    );
  }

  const keys = await api.listApiKeys(token, org.id);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">API keys</h1>
      <ApiKeysManager initialKeys={keys} orgId={org.id} />
    </div>
  );
}
