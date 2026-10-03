import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { Header } from "../../components/Header";
import { DashboardNav } from "../../components/dashboard/DashboardNav";

export default async function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  return (
    <div className="min-h-screen bg-background">
      <Header nav={<DashboardNav />} />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
