"use client";

import { useClerk } from "@clerk/nextjs";
import { useEffect } from "react";

// After an account is deleted its session is meaningless: end it in this browser.
export function SignOutOnMount() {
  const { signOut } = useClerk();
  useEffect(() => {
    void signOut();
  }, [signOut]);
  return null;
}
