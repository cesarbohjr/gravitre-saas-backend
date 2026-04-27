"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import type { Session, User } from "@supabase/supabase-js"
import { supabaseClient } from "@/lib/supabaseClient"

type AuthProfile = {
  user_id: string
  org_id: string | null
  email: string | null
  role: string | null
}

type AuthContextValue = {
  user: User | null
  session: Session | null
  profile: AuthProfile | null
  loading: boolean
  refreshSession: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function fetchProfile(token: string): Promise<AuthProfile | null> {
  try {
    const response = await fetch("/fastapi/api/auth/me", {
      headers: {
        accept: "application/json",
        authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    })
    if (!response.ok) return null
    const data = await response.json()
    return {
      user_id: String(data.user_id ?? ""),
      org_id: data.org_id ? String(data.org_id) : null,
      email: data.email ? String(data.email) : null,
      role: data.role ? String(data.role) : null,
    }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshSession = useCallback(async () => {
    setLoading(true)
    const { data } = await supabaseClient.auth.getSession()
    const nextSession = data.session ?? null
    setSession(nextSession)
    setUser(nextSession?.user ?? null)
    if (nextSession?.access_token) {
      const nextProfile = await fetchProfile(nextSession.access_token)
      setProfile(nextProfile)
    } else {
      setProfile(null)
    }
    setLoading(false)
  }, [])

  const signOut = useCallback(async () => {
    await supabaseClient.auth.signOut()
    setUser(null)
    setSession(null)
    setProfile(null)
  }, [])

  useEffect(() => {
    refreshSession()
    const { data } = supabaseClient.auth.onAuthStateChange(async (_event, nextSession) => {
      setSession(nextSession)
      setUser(nextSession?.user ?? null)
      if (nextSession?.access_token) {
        setProfile(await fetchProfile(nextSession.access_token))
      } else {
        setProfile(null)
      }
      setLoading(false)
    })
    const unauthorizedHandler = () => {
      signOut()
    }
    window.addEventListener("gravitre:unauthorized", unauthorizedHandler)
    return () => {
      data.subscription.unsubscribe()
      window.removeEventListener("gravitre:unauthorized", unauthorizedHandler)
    }
  }, [refreshSession, signOut])

  const value = useMemo<AuthContextValue>(
    () => ({ user, session, profile, loading, refreshSession, signOut }),
    [user, session, profile, loading, refreshSession, signOut]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider")
  }
  return context
}
