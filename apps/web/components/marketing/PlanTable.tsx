"use client";

import { useState } from "react";
import { annualUsd, type PlanTier, type ProductSlug } from "../../lib/nexora/catalog";
import { Card } from "../ui";

type Interval = "month" | "year";

function price(slug: ProductSlug, tier: PlanTier, interval: Interval): string {
  if (tier.monthlyUsd === 0) return "$0";
  if (interval === "month") return `$${tier.monthlyUsd}/mo`;
  return `$${annualUsd(slug, tier).toLocaleString("en-US")}/yr`;
}

export function PlanTable({ slug, tiers }: { slug: ProductSlug; tiers: PlanTier[] }) {
  const [interval, setInterval] = useState<Interval>("month");
  const options: Array<{ value: Interval; label: string }> = [
    { value: "month", label: "Monthly" },
    { value: "year", label: "Annual" },
  ];

  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Billing interval" className="inline-flex rounded-nx-md border border-nx-border-input p-0.5">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={interval === opt.value}
            onClick={() => setInterval(opt.value)}
            className={`h-8 rounded-nx-sm px-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nx-accent ${
              interval === opt.value ? "bg-nx-accent text-nx-on-accent" : "text-nx-text"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {tiers.map((tier) => (
          <li key={tier.id}>
            <Card className="h-full space-y-1 p-4">
              <h4 className="text-sm font-semibold text-nx-text">{tier.name}</h4>
              <p className="text-lg font-semibold text-nx-text">{price(slug, tier, interval)}</p>
              <p className="text-sm text-nx-text-muted">{tier.limit}</p>
              {tier.perks && <p className="text-xs text-nx-text-muted">{tier.perks}</p>}
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
