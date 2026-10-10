import Link from "next/link";

const LINKS = [
  { href: "/console", label: "Products" },
  { href: "/console/usage", label: "Usage" },
  { href: "/console/members", label: "Members" },
  { href: "/console/audit", label: "Audit log" },
  { href: "/dashboard/billing", label: "Billing" },
  { href: "/dashboard/api-keys", label: "API keys" },
  { href: "/console/account", label: "Account" },
];

export function ConsoleNav() {
  return (
    <>
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="text-nx-text-muted hover:text-nx-text hover:underline">
          {link.label}
        </Link>
      ))}
    </>
  );
}
