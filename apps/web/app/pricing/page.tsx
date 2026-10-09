import { PlatformShell } from "../../components/marketing/PlatformShell";
import { PlanTable } from "../../components/marketing/PlanTable";
import { PLANS, PRODUCTS } from "../../lib/nexora/catalog";

export const metadata = { title: "Pricing | Nexora" };

export default function PricingPage() {
  return (
    <PlatformShell>
      <div className="mx-auto w-full max-w-[1120px] space-y-12 px-4 py-12 sm:px-6">
        <div className="max-w-2xl space-y-2">
          <h1 className="text-[40px] font-bold leading-[44px] text-nx-text">Pricing</h1>
          <p className="text-nx-text-muted">Each product has its own plan. Start free, pay only for what you use.</p>
        </div>
        {PRODUCTS.map((p) => (
          <section key={p.slug} aria-labelledby={`h-${p.slug}`} className="space-y-3">
            <h2 id={`h-${p.slug}`} className="text-xl font-semibold text-nx-text">{p.name}</h2>
            {p.status !== "live" ? (
              <p className="text-sm text-nx-text-muted">
                Coming soon: these are the planned plans, and none can be bought yet.
              </p>
            ) : null}
            <PlanTable slug={p.slug} tiers={PLANS[p.slug]} />
          </section>
        ))}
      </div>
    </PlatformShell>
  );
}
