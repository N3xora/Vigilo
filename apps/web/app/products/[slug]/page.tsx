import Link from "next/link";
import { notFound } from "next/navigation";
import { GetStartedButton, PlatformShell, SecondaryLink } from "../../../components/marketing/PlatformShell";
import { PlanTable } from "../../../components/marketing/PlanTable";
import { Badge, Card } from "../../../components/ui";
import { PLANS, PRODUCTS, type ProductSlug } from "../../../lib/nexora/catalog";
import { PRODUCT_PAGES } from "../../../lib/nexora/platform";

// Vigilo has its own page at /products/vigilo (it is the product with a live
// scan form); every other product uses this template.
const SLUGS = PRODUCTS.map((p) => p.slug).filter((s) => s !== "vigilo");

export function generateStaticParams() {
  return SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = PRODUCTS.find((p) => p.slug === slug);
  const page = PRODUCT_PAGES[slug as keyof typeof PRODUCT_PAGES];
  return product && page
    ? { title: `${product.name} | Nexora`, description: page.headline }
    : {};
}

const STATUS_NOTE = {
  beta: "Beta: it is being rolled out, so scope and limits can change.",
  soon: "Coming soon: it is not open to organisations yet.",
  live: "",
} as const;

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = PRODUCTS.find((p) => p.slug === slug);
  const page = PRODUCT_PAGES[slug as keyof typeof PRODUCT_PAGES];
  if (!product || !page || product.slug === "vigilo") notFound();

  return (
    <PlatformShell>
      <article className="mx-auto w-full max-w-[1120px] space-y-12 px-4 py-16 sm:px-6">
        <header className="max-w-3xl space-y-4">
          <Link href="/products" className="text-sm text-nx-accent underline underline-offset-2">
            All products
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[40px] font-bold leading-[44px] text-nx-text">{product.name}</h1>
            <Badge tone={product.status === "beta" ? "accent" : "neutral"}>
              {product.status === "beta" ? "Beta" : "Coming soon"}
            </Badge>
            <Badge>{product.category}</Badge>
          </div>
          <p className="text-xl font-medium text-nx-text">{page.headline}</p>
          <p className="text-nx-text-muted">{page.summary}</p>
          <p className="text-sm text-nx-text-muted">{STATUS_NOTE[product.status]}</p>
          <div className="flex flex-wrap gap-3 pt-2">
            <GetStartedButton />
            <SecondaryLink href="/pricing">See pricing</SecondaryLink>
          </div>
        </header>

        <section aria-labelledby="fits" className="space-y-4">
          <h2 id="fits" className="text-[28px] font-bold leading-[34px] text-nx-text">
            How it fits into Nexora
          </h2>
          <ul className="grid gap-4 md:grid-cols-3">
            {page.fits.map((line) => (
              <li key={line}>
                <Card className="h-full">
                  <p className="text-sm text-nx-text">{line}</p>
                </Card>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="plans" className="space-y-4">
          <h2 id="plans" className="text-[28px] font-bold leading-[34px] text-nx-text">Plans</h2>
          <PlanTable slug={product.slug as ProductSlug} tiers={PLANS[product.slug]} />
        </section>
      </article>
    </PlatformShell>
  );
}
