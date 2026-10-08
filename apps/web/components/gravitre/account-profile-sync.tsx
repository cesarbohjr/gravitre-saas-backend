"use client"

import { useEffect } from "react"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import type { UserProfile } from "@/types/api"
import { useUserProfile } from "@/lib/user-profile-context"

/** Keeps local profile context aligned with the server user row (name, avatar, title, department). */
export function AccountProfileSync() {
  const { user } = useAuth()
  const { updateProfile, setAvatarImage } = useUserProfile()
  // Same key and fetcher as AppShell's /api/auth/me so SWR dedupes them into
  // one request (this used to fetch the ~1.4s endpoint a second time).
  const { data } = useSWR<UserProfile>(user ? "/api/auth/me" : null, apiFetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 60_000,
  })

  useEffect(() => {
    const serverUser = data?.user
    if (!user || !serverUser) return

    const fullName = (serverUser.full_name || "").trim()
    const [firstName, ...rest] = fullName.split(" ").filter(Boolean)
    updateProfile({
      firstName: firstName || user.email?.split("@")[0] || "User",
      lastName: rest.join(" "),
      email: serverUser.email || user.email || "",
      // Server is source of truth — clear demo localStorage leftovers when unset.
      jobTitle: (serverUser.job_title ?? "").trim(),
      department: (serverUser.department ?? "").trim(),
    })
    setAvatarImage(serverUser.avatar_url ?? null)
  }, [
    user,
    data?.user?.avatar_url,
    data?.user?.full_name,
    data?.user?.email,
    data?.user?.job_title,
    data?.user?.department,
    updateProfile,
    setAvatarImage,
  ])

  return null
}
