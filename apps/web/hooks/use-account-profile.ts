"use client"

import { useMemo } from "react"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { authApi } from "@/lib/api"
import { initialsFromDisplayName, resolveAvatarUrl } from "@/lib/user-avatar"
import { useUserProfile } from "@/lib/user-profile-context"

export function useAccountProfile() {
  const { user } = useAuth()
  const { profile, getInitials, getFullName } = useUserProfile()

  const { data, mutate, isLoading } = useSWR(
    user ? "account-profile-me" : null,
    () => authApi.me(),
    { revalidateOnFocus: false },
  )

  const serverUser = data?.user

  return useMemo(() => {
    const authName =
      (user?.user_metadata?.full_name as string | undefined) ||
      (user?.user_metadata?.name as string | undefined) ||
      user?.email?.split("@")[0] ||
      "You"

    const displayName =
      (serverUser?.full_name || "").trim() ||
      getFullName().trim() ||
      authName

    const profileSynced = Boolean(user?.email && profile.email === user.email)
    const initials =
      profileSynced && getInitials().trim()
        ? getInitials()
        : initialsFromDisplayName(displayName, user?.email ?? serverUser?.email)

    const avatarUrl = resolveAvatarUrl(
      serverUser?.avatar_url,
      profileSynced ? profile.avatarImage : null,
      user?.user_metadata?.avatar_url as string | undefined,
      user?.user_metadata?.picture as string | undefined,
    )

    return {
      displayName,
      email: serverUser?.email || user?.email || profile.email,
      avatarUrl,
      initials,
      isLoading: Boolean(user) && isLoading,
      refresh: mutate,
    }
  }, [user, serverUser, profile, getFullName, getInitials, isLoading, mutate])
}
