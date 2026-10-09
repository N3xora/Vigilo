import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { AcceptInviteForm } from "../../../components/console/AcceptInviteForm";
import { Footer } from "../../../components/Footer";
import { Header } from "../../../components/Header";
import { Card } from "../../../components/ui";

export const metadata = { title: "Join an organisation", robots: { index: false } };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const { userId } = await auth();
  if (!userId) {
    // Come back here after signing in or signing up.
    redirect(`/sign-in?redirect_url=${encodeURIComponent(`/invite/${token}`)}`);
  }

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-md flex-1 px-4 py-16">
        <Card className="space-y-4">
          <h1 className="text-xl font-semibold text-nx-text">You have been invited to an organisation</h1>
          <p className="text-sm text-nx-text-muted">
            Accepting adds you as a member. The invitation only works for the email address it was sent
            to, so sign in with that address.
          </p>
          <AcceptInviteForm token={token} />
        </Card>
      </main>
      <Footer />
    </>
  );
}
