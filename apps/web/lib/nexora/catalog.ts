// Static product catalog and plan ladders. The prices mirror the public
// pricing page; when the backend serves GET /v1/plans?product= this file
// shrinks to marketing copy only.

export type ProductSlug = "vigilo" | "sentinel" | "cspm" | "gateway" | "neurawall";
export type ProductCategory = "AI" | "Security" | "Cloud";

export interface Product {
  slug: ProductSlug;
  name: string;
  category: ProductCategory;
  status: "live" | "beta" | "soon";
  pitch: string;
  meter: string;
}

export const PRODUCTS: Product[] = [
  { slug: "vigilo", name: "Vigilo", category: "Security", status: "live", pitch: "Scan a live URL and get a security and compliance report with fixes you can paste.", meter: "scans" },
  { slug: "sentinel", name: "Sentinel", category: "Security", status: "soon", pitch: "Paste a log sample and get the handful of lines worth reading.", meter: "scans" },
  { slug: "cspm", name: "CSPM", category: "Cloud", status: "soon", pitch: "Paste a cloud configuration and get concrete misconfiguration findings.", meter: "scans" },
  { slug: "gateway", name: "Gateway", category: "AI", status: "soon", pitch: "One governed entry point for every model call your organisation makes.", meter: "requests" },
  { slug: "neurawall", name: "NeuraWall", category: "Security", status: "soon", pitch: "An AI-assisted firewall that never drops traffic without telling you.", meter: "nodes" },
];

export interface PlanTier {
  id: string;
  name: string;
  monthlyUsd: number;
  limit: string;
  perks?: string;
}

const ladder = (
  prices: [number, number, number, number],
  limits: [string, string, string, string, string],
): PlanTier[] => [
  { id: "free", name: "Free", monthlyUsd: 0, limit: limits[0] },
  { id: "starter", name: "Starter", monthlyUsd: prices[0], limit: limits[1] },
  { id: "pro", name: "Pro", monthlyUsd: prices[1], limit: limits[2] },
  { id: "business", name: "Business", monthlyUsd: prices[2], limit: limits[3], perks: "Priority support" },
  { id: "scale", name: "Scale", monthlyUsd: prices[3], limit: limits[4], perks: "Priority support and SLA" },
];

// Annual billing: ladders get 20% off, Vigilo and NeuraWall publish explicit
// annual prices (about 17% off). `annualUsd` wins when present.
export const PLANS: Record<ProductSlug, PlanTier[]> = {
  sentinel: ladder([9, 29, 79, 249], ["20 scans / mo", "150 scans / mo", "1,500 scans / mo", "7,500 scans / mo", "40,000 scans / mo"]),
  cspm: ladder([19, 49, 149, 399], ["10 scans / mo", "75 scans / mo", "750 scans / mo", "3,500 scans / mo", "20,000 scans / mo"]),
  gateway: ladder([19, 59, 199, 599], ["100 requests / mo", "1,500 requests / mo", "12,000 requests / mo", "60,000 requests / mo", "300,000 requests / mo"]),
  vigilo: [
    { id: "free", name: "Free", monthlyUsd: 0, limit: "1 target, 3 scans / mo", perks: "Passive checks" },
    { id: "pro", name: "Pro", monthlyUsd: 29, limit: "25 targets, unlimited scans", perks: "Active checks, daily monitoring, API, white-label reports" },
  ],
  neurawall: [
    { id: "community", name: "Community", monthlyUsd: 0, limit: "1 node", perks: "Self-hosted, 7-day retention" },
    { id: "pro", name: "Pro", monthlyUsd: 149, limit: "5 nodes", perks: "7-day retention, optional Claude AI" },
    { id: "business", name: "Business", monthlyUsd: 499, limit: "25 nodes", perks: "30-day retention, Claude AI included" },
    { id: "enterprise", name: "Enterprise", monthlyUsd: 3000, limit: "100 nodes", perks: "90-day retention, SLA" },
  ],
};

const ANNUAL_EXPLICIT: Partial<Record<ProductSlug, Record<string, number>>> = {
  vigilo: { pro: 290 },
  neurawall: { pro: 1490, business: 4990, enterprise: 30000 },
};

export function annualUsd(slug: ProductSlug, tier: PlanTier): number {
  const explicit = ANNUAL_EXPLICIT[slug]?.[tier.id];
  if (explicit !== undefined) return explicit;
  return Math.round(tier.monthlyUsd * 12 * 0.8 * 10) / 10;
}
