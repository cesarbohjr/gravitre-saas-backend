"use client"

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react"
import { hasSupabasePublicEnv, supabaseClient } from "@/lib/supabaseClient"
import type { User, Session } from "@supabase/supabase-js"

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)
const AUTH_INIT_TIMEOUT_MS = 5000

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Auth initialization timed out")), timeoutMs)
    promise
      .then((value) => {
        clearTimeout(timer)
        resolve(value)
      })
      .catch((error) => {
        clearTimeout(timer)
        reject(error)
      })
  })
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!hasSupabasePublicEnv) {
      setLoading(false)
      return
    }

    let active = true

    // Get initial session with timeout guard
    withTimeout(supabaseClient.auth.getSession(), AUTH_INIT_TIMEOUT_MS)
      .then(({ data: { session } }) => {
        if (!active) return
        setSession(session)
        setUser(session?.user ?? null)
      })
      .catch(() => {
        if (!active) return
        setSession(null)
        setUser(null)
      })
      .finally(() => {
        if (!active) return
        setLoading(false)
      })

    // Subscribe to auth changes
    const {
      data: { subscription },
    } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      if (!active) return
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => {
      active = false
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
  if (!hasSupabasePublicEnv) return null
  const { data: { session } } = await supabaseClient.auth.getSession()
  return session?.access_token ?? null
}
