"use client"

import { useEffect } from "react"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { authApi } from "@/lib/api"
import { useUserProfile } from "@/lib/user-profile-context"

/** Keeps local profile context aligned with the server user row (name + avatar). */
export function AccountProfileSync() {
  const { user } = useAuth()
  const { updateProfile, setAvatarImage } = useUserProfile()
  const { data } = useSWR(user ? "account-profile-me" : null, () => authApi.me(), {
    revalidateOnFocus: false,
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
    })
    setAvatarImage(serverUser.avatar_url ?? null)
  }, [
    user,
    data?.user?.avatar_url,
    data?.user?.full_name,
    data?.user?.email,
    updateProfile,
    setAvatarImage,
  ])

  return null
}
