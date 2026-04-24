"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase";

type AuthMe = {
  user_id: string;
  org_id: string | null;
  email: string | null;
};

type State =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | { status: "authenticated"; data: AuthMe };

export function IdentitySurface() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function run() {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      if (!url || !anonKey) {
        setState({ status: "unauthenticated" });
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

        if (res.status === 401) {
          setState({ status: "unauthenticated" });
          return;
        }

        if (res.status === 502) {
          setState({ status: "unauthenticated" });
          return;
        }

        if (!res.ok) {
          setState({ status: "unauthenticated" });
          return;
        }

        const data: AuthMe = await res.json();
        setState({ status: "authenticated", data });
      } catch {
        if (!cancelled) setState({ status: "unauthenticated" });
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading…</p>
        </CardContent>
      </Card>
    );
  }

  if (state.status === "unauthenticated") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Not signed in.</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Sign in via Supabase Auth (hosted or custom) to see your identity and org.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { data } = state;

  if (data.org_id == null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Signed in. Onboarding pending — contact admin for org access.
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            user_id: {data.user_id}
            {data.email ? ` · ${data.email}` : ""}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Identity</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Signed in · org: {data.org_id}
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          user_id: {data.user_id}
          {data.email ? ` · ${data.email}` : ""}
        </p>
      </CardContent>
    </Card>
  );
}
