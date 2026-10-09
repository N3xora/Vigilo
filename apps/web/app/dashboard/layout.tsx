import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { Header } from "../../components/Header";
import { DashboardNav } from "../../components/dashboard/DashboardNav";
import { OrgSwitcher } from "../../components/console/OrgSwitcher";
import { getActiveOrg, listMyOrgs } from "../../lib/nexora/data";

export default async function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  const orgs = await listMyOrgs();
  const active = await getActiveOrg();

  return (
    <>
      <Header nav={<DashboardNav />} />
      <main className="mx-auto w-full max-w-2xl px-6 py-10 space-y-6">
        <OrgSwitcher orgs={orgs} active={active} />
        {children}
      </main>
    </>
  );
}
