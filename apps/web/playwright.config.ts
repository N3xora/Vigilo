import { defineConfig, devices } from "@playwright/test";

// Needs real Clerk dev keys in the environment (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
// CLERK_SECRET_KEY). Placeholder keys do not work: clerkMiddleware redirects to
// the Clerk frontend API for a dev handshake, so every page fails to load.
// The specs skip themselves when the keys are missing.
//
// Signed-in specs also need E2E_USER_EMAIL: the address of an existing user in
// that Clerk dev instance (created by a person; tests never create users). They
// sign in with Clerk's testing helper, which needs only the email. They also
// need the API running (NEXT_PUBLIC_API_BASE_URL, default http://localhost:8000)
// with WEB_APP_URL equal to the base URL below, so CORS lets the browser in.
// Never point E2E_USER_EMAIL at a person whose data matters: the specs create
// organisations, targets, invitations and audit events in that account.
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // The signed-in specs share one Clerk user and one database (quotas, active-organisation
  // cookies, the organisation list): run them one after another.
  workers: process.env.E2E_USER_EMAIL ? 1 : undefined,
  globalSetup: "./e2e/global.setup.ts",
  use: { baseURL: BASE_URL },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } } },
  ],
  webServer: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
    ? {
        command: `npm run dev -- --port ${new URL(BASE_URL).port || 3000}`,
        url: `${BASE_URL}/pricing`,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
});
