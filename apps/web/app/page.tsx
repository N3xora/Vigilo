import Link from "next/link";
import { brand } from "../lib/brand";
import { GetStartedButton, PlatformShell, SecondaryLink } from "../components/marketing/PlatformShell";
import { Badge, Card } from "../components/ui";
import { PRODUCTS } from "../lib/nexora/catalog";
import { PLATFORM, SHARED } from "../lib/nexora/platform";

export const metadata = {
  title: `${PLATFORM.name}: ${PLATFORM.tagline}`,
  description: PLATFORM.summary,
};

const STEPS = [
  { title: "Create an account", body: "One sign-up gives you a personal workspace. Make an organisation when you want a team." },
  { title: "Turn on the products you need", body: "Enable each product for your organisation from the console. Nothing is installed." },
  { title: "Invite your team", body: "Give each person a role, then manage keys, plans and usage in one place." },
];

const STATUS_LABEL = { live: "Live", beta: "Beta", soon: "Coming soon" } as const;

export default function HomePage() {
  return (
    <PlatformShell>
      <section className="mx-auto w-full max-w-[1120px] space-y-6 px-4 py-20 sm:px-6">
        <p className="text-sm font-medium text-nx-accent">{PLATFORM.tagline}</p>
        <h1 className="max-w-3xl text-[40px] font-bold leading-[44px] text-nx-text">{PLATFORM.headline}</h1>
        <p className="max-w-2xl text-lg text-nx-text-muted">{PLATFORM.summary}</p>
        <div className="flex flex-wrap gap-3">
          <GetStartedButton />
          <SecondaryLink href="/products">Explore products</SecondaryLink>
          <SecondaryLink href={`mailto:${brand.supportEmail}`}>Talk to us</SecondaryLink>
        </div>
      </section>

      <section aria-labelledby="platform" className="border-y border-nx-border bg-nx-surface">
        <div className="mx-auto w-full max-w-[1120px] space-y-6 px-4 py-16 sm:px-6">
          <div className="max-w-2xl space-y-2">
            <h2 id="platform" className="text-[28px] font-bold leading-[34px] text-nx-text">
              The platform comes first, the products second
            </h2>
            <p className="text-nx-text-muted">
              Every product runs on the same foundation, so a new tool never means a new login, a new
              bill or a new set of keys.
            </p>
          </div>
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {SHARED.map((item) => (
              <li key={item.title}>
                <Card className="h-full space-y-2">
                  <h3 className="text-lg font-semibold text-nx-text">{item.title}</h3>
                  <p className="text-sm text-nx-text-muted">{item.body}</p>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="products" className="mx-auto w-full max-w-[1120px] space-y-6 px-4 py-16 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 id="products" className="text-[28px] font-bold leading-[34px] text-nx-text">Products</h2>
          <Link href="/products" className="text-sm text-nx-accent underline underline-offset-2">
            See all products
          </Link>
        </div>
        <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PRODUCTS.map((p) => (
            <li key={p.slug}>
              <Card className="flex h-full flex-col gap-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-nx-text">
                    <Link href={`/products/${p.slug}`} className="hover:underline">
                      {p.name}
                    </Link>
                  </h3>
                  <Badge tone={p.status === "live" ? "success" : p.status === "beta" ? "accent" : "neutral"}>
                    {STATUS_LABEL[p.status]}
                  </Badge>
                </div>
                <p className="text-sm text-nx-text-muted">{p.category}</p>
                <p className="text-sm text-nx-text">{p.pitch}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="how" className="border-t border-nx-border bg-nx-surface">
        <div className="mx-auto w-full max-w-[1120px] space-y-4 px-4 py-16 sm:px-6">
          <h2 id="how" className="text-[28px] font-bold leading-[34px] text-nx-text">How it works</h2>
          <ol className="grid gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <Card className="h-full space-y-2">
                  <p className="text-sm font-semibold text-nx-accent">Step {i + 1}</p>
                  <h3 className="text-lg font-semibold text-nx-text">{s.title}</h3>
                  <p className="text-sm text-nx-text-muted">{s.body}</p>
                </Card>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="cta" className="mx-auto w-full max-w-[1120px] space-y-4 px-4 py-20 text-center sm:px-6">
        <h2 id="cta" className="text-[28px] font-bold leading-[34px] text-nx-text">Start with one product</h2>
        <p className="text-nx-text-muted">The free scan needs no account. Everything else starts from one sign-up.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <GetStartedButton />
          <SecondaryLink href="/products/vigilo">Scan a site</SecondaryLink>
        </div>
      </section>
    </PlatformShell>
  );
}
