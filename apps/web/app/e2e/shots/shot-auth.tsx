"use client"

import type { Session, User } from "@supabase/supabase-js"

import { AuthContext } from "@/lib/auth-context"
import { SHOT_FIXTURES } from "@/lib/e2e-shot-fixtures"

/**
 * Supplies a fixed signed-in user to the surface being captured.
 *
 * Seeding a Supabase session cookie instead was tried and is not reliable
 * here: the browser client validates the token against the live auth server,
 * and AppShell bounces to /login the moment `useAuth()` reports no user — which
 * in this environment leaves the dev server for the production domain entirely.
 * Providing the context directly removes auth from the equation so a capture
 * can never silently screenshot the login page.
 */
export function ShotAuthProvider({ children }: { children: React.ReactNode }) {
  const user = SHOT_FIXTURES.__supabaseUser as unknown as User

  const session = {
    access_token: "shot-access-token",
    refresh_token: "shot-refresh-token",
    token_type: "bearer",
    expires_in: 86_400,
    expires_at: Math.floor(Date.now() / 1000) + 86_400,
    user,
  } as unknown as Session

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading: false,
        signOut: async () => {},
        refreshSession: async () => {},
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
