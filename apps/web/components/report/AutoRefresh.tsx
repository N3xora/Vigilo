"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// Re-reads the page on a timer while a report is still being built, so the
// visitor does not have to refresh by hand. Stops after `maxSeconds`.
export function AutoRefresh({ everySeconds = 3, maxSeconds = 300 }: { everySeconds?: number; maxSeconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => {
      if (Date.now() - started > maxSeconds * 1000) {
        clearInterval(id);
        return;
      }
      router.refresh();
    }, everySeconds * 1000);
    return () => clearInterval(id);
  }, [router, everySeconds, maxSeconds]);
  return null;
}
