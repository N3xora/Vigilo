"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api, ApiError } from "../../lib/api";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

/** Opens Stripe's hosted Customer Portal: cancel, update card, invoices. */
export function ManageSubscriptionButton({ orgId }: { orgId: string }) {
  const { getToken } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setError(null);
    setBusy(true);
    try {
      const token = await getToken({ template: JWT_TEMPLATE });
      if (!token) throw new ApiError(401, null);
      const { portal_url } = await api.createPortal(token, orgId);
      window.location.href = portal_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't open subscription management.");
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className="rounded-md border border-black/15 dark:border-white/25 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
      >
        {busy ? "Opening…" : "Manage or cancel"}
      </button>
      {error ? <p className="mt-1 text-xs text-severity-critical">{error}</p> : null}
    </div>
  );
}
