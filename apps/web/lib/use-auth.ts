"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase";

export type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | {
      status: "authenticated";
      token: string;
      orgId: string | null;
      userId: string;
      role: string | null;
    };

/**
 * FE-10: Session token for same-origin API calls. Never log token.
 * Use orgId === null to show "Onboarding pending" and disable workflow actions.
 */
export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function run() {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      if (!url || !anonKey) {
        if (!cancelled) setState({ status: "unauthenticated" });
        return;
      }
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (cancelled) return;
      if (!session?.access_token) {
        setState({ status: "unauthenticated" });
        return;
      }
      try {
        const res = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (cancelled) return;
        if (res.status === 401 || res.status === 502 || !res.ok) {
          setState({ status: "unauthenticated" });
          return;
        }
        const data = await res.json();
        setState({
          status: "authenticated",
          token: session.access_token,
          orgId: data.org_id ?? null,
          userId: data.user_id ?? "",
          role: data.role ?? null,
        });
      } catch {
        if (!cancelled) setState({ status: "unauthenticated" });
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
