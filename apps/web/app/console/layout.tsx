import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { Header } from "../../components/Header";
import { ConsoleNav } from "../../components/console/ConsoleNav";
import { OrgSwitcher } from "../../components/console/OrgSwitcher";
import { getActiveOrg, listMyOrgs } from "../../lib/nexora/data";

export default async function ConsoleLayout({ children }: LayoutProps<"/console">) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }
  const orgs = await listMyOrgs();
  const active = await getActiveOrg();

  return (
    <>
      <Header nav={<ConsoleNav />} />
      <main className="mx-auto w-full max-w-[1120px] space-y-6 px-4 py-10 sm:px-6">
        <OrgSwitcher orgs={orgs} active={active} />
        {children}
      </main>
    </>
  );
}
