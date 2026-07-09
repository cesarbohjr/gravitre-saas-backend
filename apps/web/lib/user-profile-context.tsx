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
  firstName: "John",
  lastName: "Doe",
  email: "john@acmecorp.com",
  phone: "+1 (555) 123-4567",
  jobTitle: "Operations Manager",
  department: "Operations",
  location: "San Francisco, CA",
  timezone: "America/Los_Angeles",
  bio: "Operations manager focused on workflow automation and AI-driven process optimization.",
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

  const updateProfile = (updates: Partial<UserProfile>) => {
    setProfile(prev => ({ ...prev, ...updates }))
  }

  const setAvatarImage = (image: string | null) => {
    setProfile(prev => ({ ...prev, avatarImage: image }))
  }

  const getInitials = () => {
    return `${profile.firstName[0] || ""}${profile.lastName[0] || ""}`.toUpperCase()
  }

  const getFullName = () => {
    return `${profile.firstName} ${profile.lastName}`.trim()
  }

  return (
    <UserProfileContext.Provider
      value={{
        profile,
        updateProfile,
        setAvatarImage,
        getInitials,
        getFullName,
      }}
    >
      {children}
    </UserProfileContext.Provider>
  )
}

export function useUserProfile() {
  const context = useContext(UserProfileContext)
  if (context === undefined) {
    throw new Error("useUserProfile must be used within a UserProfileProvider")
  }
  return context
}
