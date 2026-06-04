"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"

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
    const defaultDestination = "/operator"
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
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 px-6">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
        {errorMessage ? (
          <>
            <h1 className="text-lg font-semibold text-zinc-900">Authentication error</h1>
            <p className="mt-2 text-sm text-zinc-600">{errorMessage}</p>
            <button
              type="button"
              className="mt-5 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white"
              onClick={() => router.replace(callbackContext.fallbackDestination)}
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-emerald-600" />
            <h1 className="mt-4 text-lg font-semibold text-zinc-900">Finishing sign in</h1>
            <p className="mt-2 text-sm text-zinc-600">Please wait while we secure your session.</p>
          </>
        )}
      </div>
    </div>
  )
}

function AuthCallbackFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50">
      <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
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
