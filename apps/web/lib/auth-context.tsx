"use client"

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react"
import { supabaseClient } from "@/lib/supabaseClient"
import type { User, Session } from "@supabase/supabase-js"

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    
    // Timeout to prevent infinite loading if Supabase is misconfigured
    const timeout = setTimeout(() => {
      if (mounted && loading) {
        console.warn("[v0] Auth check timed out - Supabase may not be configured")
        setLoading(false)
      }
    }, 3000)

    // Get initial session
    supabaseClient.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    }).catch((err) => {
      console.warn("[v0] Auth session check failed:", err)
      if (mounted) setLoading(false)
    })

    // Subscribe to auth changes
    const {
      data: { subscription },
    } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => {
      mounted = false
      clearTimeout(timeout)
      subscription.unsubscribe()
    }
  }, [])

  const signOut = useCallback(async () => {
    await supabaseClient.auth.signOut()
    setUser(null)
    setSession(null)
    window.location.assign("/login")
  }, [])

  const refreshSession = useCallback(async () => {
    const { data: { session } } = await supabaseClient.auth.refreshSession()
    setSession(session)
    setUser(session?.user ?? null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut, refreshSession }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

// Helper to get access token for API requests
export async function getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabaseClient.auth.getSession()
  return session?.access_token ?? null
}
