"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"

import { APP_ROUTES } from "@/lib/app-routes"
import { markAuthTransition } from "@/lib/auth-transition"
import { supabaseClient } from "@/lib/supabaseClient"

function normalizeNextPath(nextPath: string | null, fallback: string): string {
  if (!nextPath) return fallback
  if (!nextPath.startsWith("/")) return fallback
  return nextPath
}

function AuthCallbackCompleteContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const callbackContext = useMemo(() => {
    const type = searchParams.get("type")
    const defaultDestination = APP_ROUTES.welcome
    const fallbackDestination = type === "signup" ? "/get-started" : "/login"
    const nextPath = normalizeNextPath(searchParams.get("next"), defaultDestination)
    return { type, fallbackDestination, nextPath }
  }, [searchParams])

  useEffect(() => {
    let cancelled = false

    const completeAuth = async () => {
      if (typeof window === "undefined" || !window.location.hash) {
        if (!cancelled) {
          setErrorMessage("Missing authentication response. Please try signing in again.")
        }
        return
      }

      const hashParams = new URLSearchParams(window.location.hash.slice(1))
      const accessToken = hashParams.get("access_token")
      const refreshToken = hashParams.get("refresh_token")

      if (!accessToken || !refreshToken) {
        if (!cancelled) {
          setErrorMessage("Missing authentication response. Please try signing in again.")
        }
        return
      }

      const { error } = await supabaseClient.auth.setSession({
        access_token: accessToken,
        refresh_token: refreshToken,
      })

      if (error) {
        if (!cancelled) {
          setErrorMessage("Your session could not be established. Please sign in again.")
        }
        return
      }

      markAuthTransition()
      if (!cancelled) {
        router.replace(callbackContext.nextPath)
      }
    }

    void completeAuth()
    return () => {
      cancelled = true
    }
  }, [callbackContext.nextPath, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
        {errorMessage ? (
          <>
            <h1 className="text-lg font-semibold text-foreground">Authentication error</h1>
            <p className="mt-2 text-sm text-muted-foreground">{errorMessage}</p>
            <button
              type="button"
              className="mt-5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={() => router.replace(callbackContext.fallbackDestination)}
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-brand" />
            <h1 className="mt-4 text-lg font-semibold text-foreground">Finishing sign in</h1>
            <p className="mt-2 text-sm text-muted-foreground">Please wait while we secure your session.</p>
          </>
        )}
      </div>
    </div>
  )
}

function AuthCallbackFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-brand" />
    </div>
  )
}

export default function AuthCallbackCompletePage() {
  return (
    <Suspense fallback={<AuthCallbackFallback />}>
      <AuthCallbackCompleteContent />
    </Suspense>
  )
}
