import Link from "next/link";
import { PlatformShell } from "../../components/marketing/PlatformShell";
import { Badge, Card } from "../../components/ui";
import { PRODUCTS, type ProductCategory } from "../../lib/nexora/catalog";

export const metadata = { title: "Products | Nexora" };

const CATEGORIES: ProductCategory[] = ["AI", "Security", "Cloud"];

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;
  const active = CATEGORIES.find((c) => c === category);
  const shown = active ? PRODUCTS.filter((p) => p.category === active) : PRODUCTS;
  const chip = "rounded-full border px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nx-accent";

  return (
    <PlatformShell>
      <div className="mx-auto w-full max-w-[1120px] space-y-8 px-4 py-12 sm:px-6">
        <div className="max-w-2xl space-y-2">
          <h1 className="text-[40px] font-bold leading-[44px] text-nx-text">Products</h1>
          <p className="text-nx-text-muted">Security, cloud and AI tools that share one account, one console and one API.</p>
        </div>
        <nav aria-label="Filter by category" className="flex flex-wrap gap-2">
          <Link
            href="/products"
            aria-current={active ? undefined : "page"}
            className={`${chip} ${active ? "border-nx-border-input text-nx-text" : "border-nx-accent bg-nx-accent-soft text-nx-on-accent-soft"}`}
          >
            All
          </Link>
          {CATEGORIES.map((c) => (
            <Link
              key={c}
              href={`/products?category=${c}`}
              aria-current={active === c ? "page" : undefined}
              className={`${chip} ${active === c ? "border-nx-accent bg-nx-accent-soft text-nx-on-accent-soft" : "border-nx-border-input text-nx-text"}`}
            >
              {c}
            </Link>
          ))}
        </nav>
        {shown.length === 0 ? (
          <p className="text-nx-text-muted">Nothing in this category yet.</p>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {shown.map((p) => (
              <li key={p.slug} id={p.slug}>
                <Card className="h-full space-y-2">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-nx-text">
                      <Link href={`/products/${p.slug}`} className="hover:underline">
                        {p.name}
                      </Link>
                    </h2>
                    <Badge tone={p.status === "live" ? "success" : p.status === "beta" ? "accent" : "neutral"}>
                      {p.status === "live" ? "Live" : p.status === "beta" ? "Beta" : "Coming soon"}
                    </Badge>
                  </div>
                  <p className="text-sm text-nx-text-muted">{p.category}</p>
                  <p className="text-nx-text">{p.pitch}</p>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PlatformShell>
  );
}
