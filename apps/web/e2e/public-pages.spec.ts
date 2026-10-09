import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.skip(
  !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || !process.env.CLERK_SECRET_KEY,
  "needs Clerk dev keys (see playwright.config.ts)",
);

async function guard(page: Page) {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.status() >= 500) problems.push(`${r.status()} ${r.url()}`);
  });
  return problems;
}

test("F01-H1 pricing lists every product and toggles annual prices", async ({ page }) => {
  const problems = await guard(page);
  await page.goto("/pricing");
  await expect(page.getByRole("heading", { level: 1, name: "Pricing" })).toBeVisible();
  for (const name of ["Vigilo", "Sentinel", "CSPM", "Gateway", "NeuraWall"]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }
  const vigilo = page.getByRole("region", { name: "Vigilo" });
  await expect(vigilo.getByText("$29/mo")).toBeVisible();
  await vigilo.getByRole("radio", { name: "Annual" }).click();
  await expect(vigilo.getByText("$290/yr")).toBeVisible();
  expect(problems).toEqual([]);
});

test("F01-H2 products page shows status badges", async ({ page }) => {
  const problems = await guard(page);
  await page.goto("/products");
  await expect(page.getByRole("heading", { level: 2, name: "Vigilo" })).toBeVisible();
  await expect(page.getByText("Live", { exact: true })).toBeVisible();
  await expect(page.getByText("Coming soon", { exact: true }).first()).toBeVisible();
  expect(problems).toEqual([]);
});

test("F01-E1 no horizontal scroll at this viewport", async ({ page }) => {
  await guard(page);
  for (const path of ["/pricing", "/products"]) {
    await page.goto(path);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});

test("F01-E2 keyboard can reach and flip the billing interval", async ({ page }) => {
  await guard(page);
  await page.goto("/pricing");
  const annual = page.getByRole("region", { name: "Sentinel" }).getByRole("radio", { name: "Annual" });
  await annual.focus();
  await page.keyboard.press("Enter");
  await expect(annual).toHaveAttribute("aria-checked", "true");
});

test("F01-H4 home leads to the products and to sign-up", async ({ page }) => {
  const problems = await guard(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("One account");
  await expect(page.getByRole("link", { name: "Explore products" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get started" }).first()).toHaveAttribute(
    "href",
    "/sign-up",
  );
  for (const name of ["Vigilo", "Sentinel", "CSPM", "Gateway", "NeuraWall"]) {
    await expect(page.getByRole("link", { name })).toBeVisible();
  }
  expect(problems).toEqual([]);
});

test("F01-H5 a product page shows its plans and a way in", async ({ page }) => {
  const problems = await guard(page);
  await page.goto("/products/sentinel");
  await expect(page.getByRole("heading", { level: 1, name: /Sentinel/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Plans" })).toBeVisible();
  await expect(page.getByText("$29/mo")).toBeVisible();
  await expect(page.getByRole("link", { name: "See pricing" })).toBeVisible();
  expect(problems).toEqual([]);
});

test("F01-H6 the Vigilo page keeps the scan form", async ({ page }) => {
  await guard(page);
  await page.goto("/products/vigilo");
  await expect(page.getByLabel(/URL|site/i).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Scan it" })).toBeVisible();
});

test("F01-E3 category filter narrows the product list", async ({ page }) => {
  await guard(page);
  await page.goto("/products?category=AI");
  await expect(page.getByRole("heading", { level: 2, name: "Gateway" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Sentinel" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "AI" })).toHaveAttribute("aria-current", "page");
});

test("F01-N1 an unknown product is a 404, and Vigilo is not served by the template", async ({
  page,
}) => {
  await guard(page);
  const missing = await page.goto("/products/does-not-exist");
  expect(missing?.status()).toBe(404);
});

for (const path of ["/", "/pricing", "/products", "/products/sentinel", "/products/vigilo"]) {
  test(`A11Y axe scan ${path}`, async ({ page }) => {
    await guard(page);
    await page.goto(path);
    const results = await new AxeBuilder({ page } as ConstructorParameters<typeof AxeBuilder>[0]).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
}

test("F01-H9 trust page lists practices and is accessible", async ({ page }) => {
  const problems = await guard(page);
  await page.goto("/trust");
  await expect(page.getByRole("heading", { level: 1, name: "Trust and security" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Audit trail" })).toBeVisible();
  const results = await new AxeBuilder({ page } as ConstructorParameters<typeof AxeBuilder>[0]).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
  await expect(page.getByRole("link", { name: "Trust and security" })).toBeVisible();
  expect(problems).toEqual([]);
});
