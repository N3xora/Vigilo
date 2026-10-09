import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { expectNoProblems, signIn, skipUnlessSignedInTestsConfigured, watch } from "./auth";

skipUnlessSignedInTestsConfigured();

// One signed-in browser session at a time: these specs share one Clerk user and
// one database. Mutating specs run on desktop only; the mobile project just
// checks layout and accessibility.
test.describe.configure({ mode: "serial" });

const RUN = Date.now().toString(36);
const desktopOnly = (testInfo: { project: { name: string } }) => testInfo.project.name !== "desktop";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("S-IN-1 signed-out visitors are sent to sign in", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/console");
  await expect(page).toHaveURL(/sign-in/);
  await context.close();
});

test("S-IN-2 the console shows the five products and the personal workspace", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/console");
  await expect(page.getByRole("heading", { level: 1, name: "Your products" })).toBeVisible();
  await expect(page.getByLabel("Organisation")).toBeVisible();
  for (const name of ["Vigilo", "Sentinel", "CSPM", "Gateway", "NeuraWall"]) {
    await expect(page.getByRole("heading", { level: 3, name })).toBeVisible();
  }
  await expect(page.getByText("Enabled", { exact: true })).toBeVisible(); // Vigilo
  await expectNoProblems(problems);
});

test("S-IN-3 usage, members, audit log and account pages render", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/console/usage");
  await expect(page.getByRole("heading", { level: 1, name: "Usage" })).toBeVisible();
  await page.goto("/console/members");
  await expect(page.getByRole("heading", { level: 1, name: "Members" })).toBeVisible();
  await expect(page.getByText("(you)")).toBeVisible();
  await page.goto("/console/audit");
  await expect(page.getByRole("heading", { level: 1, name: "Audit log" })).toBeVisible();
  await page.goto("/console/account");
  await expect(page.getByRole("heading", { level: 1, name: "Your account" })).toBeVisible();
  await expectNoProblems(problems);
});

test("S-IN-4 dashboard pages render for a free account", async ({ page }) => {
  const problems = watch(page);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  await page.goto("/dashboard/targets");
  await expect(page.getByRole("heading", { level: 1, name: "Targets" })).toBeVisible();
  await page.goto("/dashboard/api-keys");
  await expect(page.getByRole("heading", { level: 1, name: "API keys" })).toBeVisible();
  await page.goto("/dashboard/branding");
  await expect(page.getByRole("heading", { level: 1, name: "Branding" })).toBeVisible();
  await page.goto("/dashboard/billing");
  await expect(page.getByRole("heading", { level: 1, name: "Billing" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /pays for/ })).toBeVisible();
  await expectNoProblems(problems);
});

for (const path of [
  "/console",
  "/console/usage",
  "/console/members",
  "/console/audit",
  "/console/account",
  "/console/new-org",
  "/dashboard",
  "/dashboard/targets",
  "/dashboard/api-keys",
  "/dashboard/billing",
]) {
  test(`S-A11Y axe scan ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page } as ConstructorParameters<typeof AxeBuilder>[0])
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(
      results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(" | ")})`),
    ).toEqual([]);
  });

  test(`S-MOBILE no horizontal scroll on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  });
}

test("S-IN-5 creating an organisation switches to it and keeps its data apart", async ({ page }, testInfo) => {
  test.skip(desktopOnly(testInfo), "mutating: desktop only");
  const problems = watch(page);
  await page.goto("/console/new-org");
  await page.getByLabel("Name").fill(`E2E team ${RUN}`);
  await page.getByLabel("Address").fill(`e2e-${RUN}`);
  await page.getByRole("button", { name: "Create organisation" }).click();
  await expect(page).toHaveURL(/\/console$/);
  await expect(page.getByLabel("Organisation")).toContainText(`E2E team ${RUN}`);

  // a duplicate address is refused with a readable message
  await page.goto("/console/new-org");
  await page.getByLabel("Name").fill("Other");
  await page.getByLabel("Address").fill(`e2e-${RUN}`);
  await page.getByRole("button", { name: "Create organisation" }).click();
  // Next also renders its own route announcer with role=alert, so match ours by text.
  await expect(page.getByRole("alert").filter({ hasText: "taken" })).toBeVisible();
  await expectNoProblems(problems);
});

test("S-IN-6 inviting someone shows a one-time link, lists it, and can withdraw it", async ({ page }, testInfo) => {
  test.skip(desktopOnly(testInfo), "mutating: desktop only");
  const problems = watch(page);
  await page.goto("/console/members");
  const address = `invitee-${RUN}@example.com`;
  await page.getByLabel("Email address").fill(address);
  await page.getByRole("button", { name: "Create invitation" }).click();
  const status = page.getByRole("status").filter({ hasText: address });
  await expect(status).toBeVisible();
  // email is not configured here, and the page must say so instead of claiming it sent
  await expect(status).toContainText(/not set up|could not be sent|did not email/i);
  await expect(status.getByLabel("Invitation link")).toHaveValue(/\/invite\/nxi_/);

  await page.reload();
  const pending = page.getByRole("region", { name: "Waiting to join" }).or(page.locator("section", { hasText: "Waiting to join" }));
  await expect(pending).toContainText(address);
  await pending.getByRole("button", { name: "Withdraw" }).first().click();
  await expect(page.locator("main")).not.toContainText(address);
  await expectNoProblems(problems);
});

test("S-IN-7 adding a target, and the audit log records it", async ({ page }, testInfo) => {
  test.skip(desktopOnly(testInfo), "mutating: desktop only");
  const problems = watch(page);
  const origin = `https://e2e-${RUN}.example.com`;
  // A fresh organisation each run: the free plan allows one target per organisation,
  // so reusing the personal one would fail on the second run.
  await page.goto("/console/new-org");
  await page.getByLabel("Name").fill(`E2E targets ${RUN}`);
  await page.getByLabel("Address").fill(`e2e-t-${RUN}`);
  await page.getByRole("button", { name: "Create organisation" }).click();
  await expect(page).toHaveURL(/\/console$/);
  await page.goto("/dashboard/targets");
  await page.getByPlaceholder(/https?:\/\//).first().fill(origin);
  await page.getByRole("button", { name: /^add/i }).click();
  await expect(page.getByText(origin)).toBeVisible();

  await page.goto("/console/audit");
  await expect(page.getByRole("table")).toContainText(`Added target ${origin}`);
  await page.getByLabel("Show").selectOption("target_added");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("table")).toContainText("Added target");
  await expect(page.getByRole("table")).not.toContainText("Created the organisation");
  await expectNoProblems(problems);
});

test("S-IN-8 free plan: API keys and checkout fail politely", async ({ page }, testInfo) => {
  test.skip(desktopOnly(testInfo), "mutating: desktop only");
  const problems = watch(page);
  await page.goto("/dashboard/api-keys");
  await page.getByPlaceholder("CI pipeline").fill("e2e key");
  await page.getByLabel("scan:read").check();
  await page.getByRole("button", { name: "Create key" }).click();
  await expect(page.locator("main")).toContainText(/limit|plan|upgrade/i);

  await page.goto("/dashboard/billing");
  await page.getByRole("button", { name: "Upgrade monthly" }).click();
  // Stripe is not configured here: a readable error, never a blank page or a crash
  await expect(page.locator("main")).toContainText(/couldn.t start checkout|not configured|error/i);
  // The 500 from checkout is the API saying Stripe is not configured (a deliberate
  // BILLING_PROVIDER_ERROR); what matters is that the page showed it readably, above.
  await expectNoProblems(
    problems.filter(
      (p) => !p.startsWith("console: Failed to load resource") && !p.endsWith("/v1/billing/checkout"),
    ),
  );
});

test("S-IN-9 account deletion asks for the exact email and does nothing without it", async ({ page }, testInfo) => {
  test.skip(desktopOnly(testInfo), "mutating form: desktop only");
  await page.goto("/console/account");
  // never submit a correct confirmation: this is a real person's account
  await page.getByLabel(/Type .* to confirm/).fill("not-my-address@example.com");
  await page.getByRole("button", { name: "Delete my account permanently" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /not the email address/i })).toBeVisible();
  await page.goto("/console");
  await expect(page.getByRole("heading", { level: 1, name: "Your products" })).toBeVisible();
});
