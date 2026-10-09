import { clerkSetup } from "@clerk/testing/playwright";

// Fetches Clerk's testing token once so sign-in is not blocked by bot detection.
// Does nothing without the keys, so the public specs and CI without secrets are unaffected.
export default async function globalSetup() {
  if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY) {
    await clerkSetup();
  }
}
