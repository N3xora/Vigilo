import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../../lib/api";
import { getActiveOrg } from "../../../lib/nexora/data";
import type { PlanResponse } from "../../../lib/types";
import { UpgradeButton } from "../../../components/dashboard/UpgradeButton";
import { BillingOverview } from "../../../components/dashboard/BillingOverview";
import { ManageSubscriptionButton } from "../../../components/dashboard/ManageSubscriptionButton";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

const PLAN_ORDER = ["free", "pro"];

function formatLimit(value: number | null): string {
  return value === null ? "Unlimited" : String(value);
}

function formatAmount(plan: PlanResponse, cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: plan.currency.toUpperCase(),
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

function formatPrice(plan: PlanResponse): string {
  if (plan.price_cents === 0) return "Free";
  const monthly = `${formatAmount(plan, plan.price_cents)} / month`;
  return plan.price_cents_yearly > 0
    ? `${monthly} or ${formatAmount(plan, plan.price_cents_yearly)} / year`
    : monthly;
}

function formatBool(value: boolean): string {
  return value ? "Included" : "—";
}

const ROWS: { label: string; render: (plan: PlanResponse) => string }[] = [
  { label: "Price", render: formatPrice },
  { label: "Targets", render: (p) => formatLimit(p.targets_limit) },
  { label: "Scans / month", render: (p) => formatLimit(p.scans_per_month_limit) },
  { label: "Active-tier scanning", render: (p) => formatBool(p.active_tier_allowed) },
  { label: "Share links", render: (p) => formatBool(p.share_links_allowed) },
  { label: "Monitoring", render: (p) => p.monitoring_frequency ?? "—" },
  { label: "Monitors", render: (p) => formatLimit(p.monitors_limit) },
  { label: "API keys", render: (p) => formatLimit(p.api_keys_limit) },
  {
    label: "API rate limit",
    render: (p) => (p.api_rate_limit_per_minute === null ? "—" : `${p.api_rate_limit_per_minute}/min`),
  },
  { label: "White-label reports", render: (p) => formatBool(p.white_label_allowed) },
];

export default async function DashboardBillingPage({
  searchParams,
}: {
  searchParams: Promise<{ checkout?: string }>;
}) {
  const { checkout } = await searchParams;
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  // The plan belongs to the active organisation, not to the person.
  const [org, plans] = await Promise.all([getActiveOrg(), api.listPlans()]);
  const currentPlanId = org.entitlements.plan_id;
  const canManageBilling = org.role === "owner" || org.role === "admin";
  const summary = canManageBilling ? await api.getBillingSummary(token, org.id) : null;
  const sortedPlans = PLAN_ORDER.map((id) => plans.find((plan) => plan.plan_id === id)).filter(
    (plan): plan is PlanResponse => plan !== undefined,
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="mt-1 text-sm text-black/60 dark:text-white/60">
          Plan for {org.name}. Everyone in the organisation gets these limits.
        </p>
      </div>

      {!canManageBilling ? (
        <p className="rounded-md border border-black/10 dark:border-white/20 p-3 text-sm">
          Only owners and admins of {org.name} can change its plan.
        </p>
      ) : null}

      {summary ? <BillingOverview summary={summary} /> : null}

      {checkout === "success" ? (
        <p className="rounded-md border border-black/10 dark:border-white/20 p-3 text-sm">
          Payment received — your plan updates within a minute. Refresh if it still shows Free.
        </p>
      ) : null}

      <h2 id="plans" className="text-xl font-semibold">
        Vigilo plans
      </h2>
      <div
        tabIndex={0}
        role="region"
        aria-label="Vigilo plan comparison"
        className="relative overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nx-accent"
      >
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-black/10 dark:border-white/20">
              <th className="text-left py-2 pr-4 font-medium text-black/60 dark:text-white/60">
                Plan
              </th>
              {sortedPlans.map((plan) => (
                <th key={plan.plan_id} className="text-left py-2 px-4 font-semibold capitalize">
                  {plan.plan_id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label} className="border-b border-black/10 dark:border-white/10">
                <td className="py-2 pr-4 text-black/60 dark:text-white/60">{row.label}</td>
                {sortedPlans.map((plan) => (
                  <td key={plan.plan_id} className="py-2 px-4">
                    {row.render(plan)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td className="py-3 pr-4" />
              {sortedPlans.map((plan) => (
                <td key={plan.plan_id} className="py-3 px-4">
                  {plan.plan_id === currentPlanId ? (
                    <div className="space-y-2">
                      <span className="text-xs text-black/60 dark:text-white/65">Current plan</span>
                      {plan.plan_id !== "free" && canManageBilling ? (
                        <ManageSubscriptionButton orgId={org.id} />
                      ) : null}
                    </div>
                  ) : plan.plan_id === "free" || !canManageBilling ? null : (
                    <div className="flex flex-wrap gap-2">
                      <UpgradeButton planId={plan.plan_id} orgId={org.id} label="Upgrade monthly" />
                      {plan.price_cents_yearly > 0 ? (
                        <UpgradeButton
                          planId={plan.plan_id}
                          orgId={org.id}
                          interval="year"
                          label="Yearly — 2 months free"
                        />
                      ) : null}
                    </div>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="text-xs text-black/60 dark:text-white/65 max-w-prose">
        Billed monthly or yearly through Stripe. Cancel any time with &ldquo;Manage or cancel&rdquo; &mdash;
        you keep Pro until the end of the period you&rsquo;ve paid for.
      </p>
    </div>
  );
}
