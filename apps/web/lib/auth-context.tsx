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
  const [loading, setLoading] = useState(hasSupabasePublicEnv)

  useEffect(() => {
    if (!hasSupabasePublicEnv) {
      return
    }

    let mounted = true

    // Validate with Supabase before trusting local session storage.
    withTimeout(supabaseClient.auth.getUser(), AUTH_INIT_TIMEOUT_MS)
      .then(({ data: { user } }) => {
        if (!mounted) return
        setUser(user ?? null)
        if (user) {
          void supabaseClient.auth.getSession().then(({ data: { session } }) => {
            if (!mounted) return
            setSession(session)
          })
        } else {
          setSession(null)
        }
      })
      .catch((err) => {
        console.warn("[v0] Auth session check failed:", err)
        if (!mounted) return
        setSession(null)
        setUser(null)
      })
      .finally(() => {
        if (!mounted) return
        setLoading(false)
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
  
  try {
    const {
      data: { user },
      error: userError,
    } = await supabaseClient.auth.getUser()

    if (userError || !user) {
      return null
    }

    const {
      data: { session },
      error,
    } = await supabaseClient.auth.getSession()

    if (error) {
      console.warn("[v0] getAccessToken error:", error.message)
      return null
    }

    if (!session) {
      const {
        data: { session: refreshedSession },
        error: refreshError,
      } = await supabaseClient.auth.refreshSession()

      if (refreshError) {
        console.warn("[v0] Session refresh failed:", refreshError.message)
        return null
      }

      return refreshedSession?.access_token ?? null
    }

    return session.access_token
  } catch (err) {
    console.warn("[v0] getAccessToken exception:", err)
    return null
  }
}
