"use client"

import { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from "react"

interface UserProfile {
  firstName: string
  lastName: string
  email: string
  phone: string
  jobTitle: string
  department: string
  location: string
  timezone: string
  bio: string
  avatarImage: string | null
}

interface UserProfileContextType {
  profile: UserProfile
  updateProfile: (updates: Partial<UserProfile>) => void
  setAvatarImage: (image: string | null) => void
  getInitials: () => string
  getFullName: () => string
}

const defaultProfile: UserProfile = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  jobTitle: "",
  department: "",
  location: "",
  timezone: "",
  bio: "",
  avatarImage: null,
}

const UserProfileContext = createContext<UserProfileContextType | undefined>(undefined)

const STORAGE_KEY = "gravitre-user-profile"

export function UserProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile>(() => {
    if (typeof window === "undefined") {
      return defaultProfile
    }
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return defaultProfile
    try {
      const parsed = JSON.parse(stored)
      return { ...defaultProfile, ...parsed }
    } catch {
      return defaultProfile
    }
  })

  // Save profile to localStorage when it changes
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  }, [profile])

  // Stable identities so consumers that depend on these in effect deps
  // (e.g. AccountProfileSync) don't trigger an infinite render loop.
  const updateProfile = useCallback((updates: Partial<UserProfile>) => {
    setProfile(prev => ({ ...prev, ...updates }))
  }, [])

  const setAvatarImage = useCallback((image: string | null) => {
    setProfile(prev => ({ ...prev, avatarImage: image }))
  }, [])

  const getInitials = useCallback(() => {
    return `${profile.firstName[0] || ""}${profile.lastName[0] || ""}`.toUpperCase()
  }, [profile.firstName, profile.lastName])

  const getFullName = useCallback(() => {
    return `${profile.firstName} ${profile.lastName}`.trim()
  }, [profile.firstName, profile.lastName])

  // Memoize the context value so its identity only changes when its
  // contents actually change, preventing needless consumer re-renders.
  const value = useMemo(
    () => ({
      profile,
      updateProfile,
      setAvatarImage,
      getInitials,
      getFullName,
    }),
    [profile, updateProfile, setAvatarImage, getInitials, getFullName],
  )

  return <UserProfileContext.Provider value={value}>{children}</UserProfileContext.Provider>
}

export function useUserProfile() {
  const context = useContext(UserProfileContext)
  if (context === undefined) {
    throw new Error("useUserProfile must be used within a UserProfileProvider")
  }
  return context
}
