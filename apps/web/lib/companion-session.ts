/**
 * Separate sign-in for the desktop app and the browser extension.
 *
 * Each companion gets its own Supabase session (its own refresh token), so it
 * can stay signed in past the web token's one-hour lifetime without fighting
 * the web app over refresh-token rotation. Renewed by the companion through
 * POST /api/auth/companion-refresh.
 */
export type CompanionSession = {
  accessToken: string
  refreshToken: string
  expiresAt: number | null
}

export async function createCompanionSession(
  webAccessToken: string,
  client: "desktop" | "extension",
): Promise<CompanionSession> {
  const res = await fetch("/api/auth/companion-session", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${webAccessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ client }),
  })
  const body = (await res.json().catch(() => ({}))) as {
    access_token?: string
    refresh_token?: string
    expires_at?: number
    detail?: string
  }
  if (!res.ok || !body.access_token || !body.refresh_token) {
    throw new Error(body.detail || "Could not create a session for this device. Try again.")
  }
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresAt: typeof body.expires_at === "number" ? body.expires_at : null,
  }
}
