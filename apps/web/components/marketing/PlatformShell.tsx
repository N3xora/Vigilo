import type { ReactNode } from "react";
import Link from "next/link";
import { Show } from "@clerk/nextjs";
import { PLATFORM } from "../../lib/nexora/platform";
import { Footer } from "../Footer";
import { Header } from "../Header";

function PlatformNav() {
  const link = "text-nx-text-muted hover:text-nx-text hover:underline";
  return (
    <>
      <Link href="/products" className={link}>
        Products
      </Link>
      <Link href="/pricing" className={link}>
        Pricing
      </Link>
      <Show when="signed-in">
        <Link href="/console" className={link}>
          Console
        </Link>
      </Show>
    </>
  );
}

// Header, content and footer for the public Nexora pages.
export function PlatformShell({ children }: { children: ReactNode }) {
  return (
    <>
      <Header nav={<PlatformNav />} name={PLATFORM.name} />
      <main className="flex-1">{children}</main>
      <Footer name={PLATFORM.name} />
    </>
  );
}

const CTA =
  "inline-flex h-12 items-center rounded-nx-md px-6 text-base font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nx-accent";

export function GetStartedButton({ label = "Get started" }: { label?: string }) {
  return (
    <>
      <Show when="signed-out">
        <Link href="/sign-up" className={`${CTA} bg-nx-accent text-nx-on-accent`}>
          {label}
        </Link>
      </Show>
      <Show when="signed-in">
        <Link href="/console" className={`${CTA} bg-nx-accent text-nx-on-accent`}>
          Open the console
        </Link>
      </Show>
    </>
  );
}

export function SecondaryLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={`${CTA} border border-nx-border-input text-nx-text hover:bg-nx-surface`}>
      {children}
    </Link>
  );
}
