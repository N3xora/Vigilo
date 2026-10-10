import type { ReactNode } from "react";
import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";
import { brand } from "../lib/brand";

export function Header({
  nav,
  name,
  href = "/",
}: {
  nav?: ReactNode;
  name?: string;
  href?: string;
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-4 border-b border-black/10 dark:border-white/10">
      <Link href={href} className="font-semibold">
        {name ?? brand.name}
      </Link>
      <nav className="flex flex-wrap items-center justify-end gap-x-4 gap-y-1 text-sm">
        {nav}
        <Show when="signed-out">
          <Link href="/sign-in">Sign in</Link>
        </Show>
        <Show when="signed-in">
          <UserButton />
        </Show>
      </nav>
    </header>
  );
}
