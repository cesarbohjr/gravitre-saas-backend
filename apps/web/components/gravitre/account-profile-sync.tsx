"use client"

import { useEffect } from "react"
import useSWR from "swr"
import { useTheme } from "next-themes"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { applyCompactTables, type AuthMeResponse } from "@/lib/settings-api/profile"
import { useUserProfile } from "@/lib/user-profile-context"

/**
 * Keeps local profile context aligned with the server user row (name, avatar,
 * title, department, phone, location, time zone, bio) and applies the person's
 * display preferences app wide: Compact tables and a System theme.
 */
export function AccountProfileSync() {
  const { user } = useAuth()
  const { updateProfile, setAvatarImage } = useUserProfile()
  const { setTheme } = useTheme()
  // Same key and fetcher as AppShell's /api/auth/me so SWR dedupes them into
  // one request (this used to fetch the ~1.4s endpoint a second time).
  const { data } = useSWR<AuthMeResponse>(user ? "/api/auth/me" : null, apiFetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 60_000,
  })

  useEffect(() => {
    const serverUser = data?.user
    if (!user || !serverUser) return

    const fullName = (serverUser.full_name || "").trim()
    const [firstName, ...rest] = fullName.split(" ").filter(Boolean)
    // Phone, location, time zone and bio only overwrite the local copy once the
    // server has a value, so anything typed before they were saved server side
    // survives until the person saves it on the Profile page.
    const extras = Object.fromEntries(
      (["phone", "location", "timezone", "bio"] as const)
        .map((key) => [key, (serverUser[key] ?? "").trim()] as const)
        .filter(([, value]) => value),
    )
    updateProfile({
      firstName: firstName || user.email?.split("@")[0] || "User",
      lastName: rest.join(" "),
      email: serverUser.email || user.email || "",
      // Server is source of truth — clear demo localStorage leftovers when unset.
      jobTitle: (serverUser.job_title ?? "").trim(),
      department: (serverUser.department ?? "").trim(),
      ...extras,
    })
    setAvatarImage(serverUser.avatar_url ?? null)
  }, [
    user,
    data?.user,
    updateProfile,
    setAvatarImage,
  ])

  const compactTables = data?.user?.preferences?.compact_tables
  useEffect(() => {
    if (compactTables === undefined) return
    applyCompactTables(Boolean(compactTables))
  }, [compactTables])

  // Light and Dark are kept per device by next-themes. "System" is the one
  // choice that needs the saved preference: follow the OS while it is set.
  const themePreference = data?.user?.preferences?.theme
  useEffect(() => {
    if (themePreference !== "system" || typeof window === "undefined" || !window.matchMedia) return
    const query = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => setTheme(query.matches ? "dark" : "light")
    apply()
    query.addEventListener?.("change", apply)
    return () => query.removeEventListener?.("change", apply)
  }, [themePreference, setTheme])

  return null
}
