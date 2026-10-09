import Link from "next/link";
import { Show } from "@clerk/nextjs";
import { Header } from "../../../components/Header";
import { ScanSubmitForm } from "../../../components/ScanSubmitForm";
import { Footer } from "../../../components/Footer";
import { LandingSections } from "../../../components/marketing/LandingSections";
import { brand } from "../../../lib/brand";

export const metadata = {
  title: `${brand.name}: ${brand.shortDescription}`,
  description: brand.shortDescription,
};

function VigiloNav() {
  return (
    <>
      <Link href="/products" className="text-black/60 dark:text-white/60 hover:underline">
        All products
      </Link>
      <Link href="/pricing" className="text-black/60 dark:text-white/60 hover:underline">
        Pricing
      </Link>
      <Show when="signed-in">
        <Link href="/dashboard">Dashboard</Link>
      </Show>
    </>
  );
}

export default function VigiloPage() {
  return (
    <>
      <Header nav={<VigiloNav />} href="/products/vigilo" />
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <div className="max-w-lg space-y-2">
          <p className="text-sm font-medium text-nx-accent">{brand.tagline}</p>
          <h1 className="text-3xl font-bold">Other scanners bury you in alerts. {brand.name} shows only what it can prove.</h1>
          <p className="text-black/60 dark:text-white/60">
            Paste your live URL. Get a plain-language report where every problem carries its
            evidence and a fix you can paste into your AI coding tool.
          </p>
        </div>
        <ScanSubmitForm />
      </main>
      <LandingSections />
      <Footer />
    </>
  );
}
