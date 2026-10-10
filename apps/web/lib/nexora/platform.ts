// Marketing copy for the platform and its products. The platform name is not in
// brand.config.json yet (it still names the Vigilo product); keeping it here
// means a rename is one edit once the name is cleared (see replica/brand.md).
import type { ProductSlug } from "./catalog";

export const PLATFORM = {
  name: "Nexora",
  tagline: "Build. Secure. Operate.",
  headline: "One account for the tools that build, secure and operate your software",
  summary:
    "Security scanning, log analysis, cloud checks and AI model governance, on one account, one console and one API.",
} as const;

export const SHARED = [
  { title: "One account", body: "Sign in once. Every product uses the same identity." },
  { title: "Organisations and roles", body: "Invite your team and give each person viewer, member or admin access." },
  { title: "One set of API keys", body: "Create keys for your organisation, not for one person, so they outlive staff changes." },
  { title: "One bill", body: "Each organisation has its own plan and its own invoices." },
  { title: "Usage in one place", body: "See what each product has used this month against your plan." },
] as const;

export interface ProductPage {
  headline: string;
  summary: string;
  fits: string[];
}

// Written to the level of what each product's one-line description promises,
// and no further: no feature lists beyond what that line supports.
export const PRODUCT_PAGES: Record<Exclude<ProductSlug, "vigilo">, ProductPage> = {
  sentinel: {
    headline: "Paste a log sample, find the ten lines worth reading",
    summary:
      "Logs are long and most of them are noise. Sentinel reads a sample you give it and points to the few lines that deserve a human's attention.",
    fits: [
      "Runs under your organisation, so teammates see the same results.",
      "Usage counts against your Sentinel plan, visible next to your other products.",
      "Reachable from the same API keys as everything else you use.",
    ],
  },
  cspm: {
    headline: "Paste your cloud config, get real findings back",
    summary:
      "Cloud misconfiguration is easy to introduce and hard to spot. CSPM checks the configuration you give it and reports what is actually wrong.",
    fits: [
      "Findings belong to your organisation, not to one person's login.",
      "Plan and usage sit beside your other products.",
      "One set of API keys, one place to manage who can see what.",
    ],
  },
  gateway: {
    headline: "A governed front door for every model call your organisation makes",
    summary:
      "When many people and services call language models, you want one place that decides who may call what. Gateway is that front door.",
    fits: [
      "Access follows your organisation's roles.",
      "Requests are metered per organisation against your Gateway plan.",
      "Managed with the same API keys and the same billing as the rest of Nexora.",
    ],
  },
  neurawall: {
    headline: "An AI-assisted firewall that never lets a model silently drop your traffic",
    summary:
      "AI can help decide what a firewall should do, but it should never decide in the dark. NeuraWall keeps a model's choices visible so traffic is not dropped without you knowing.",
    fits: [
      "Priced by the number of nodes you run.",
      "Part of the same organisation, roles and billing as your other products.",
      "Community edition is self-hosted; paid editions add retention and support.",
    ],
  },
};
