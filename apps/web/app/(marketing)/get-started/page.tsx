"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Eye, EyeOff, Loader2, Github, Check } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { beginOAuthSignIn } from "@/lib/oauth"
import { onboardingApi, billingApi } from "@/lib/api"
import { getAuthRedirectUrl } from "@/lib/auth-redirect"
import { supabaseClient } from "@/lib/supabaseClient"

// Human-readable error messages
function humanizeAuthError(message: string): string {
  const lower = message.toLowerCase()
  if (lower.includes("already registered") || lower.includes("already been registered")) {
    return "An account with this email already exists. Sign in instead."
  }
  if (lower.includes("invalid login credentials")) {
    return "That email and password don't match."
  }
  if (lower.includes("password should be at least")) {
    return "Password must be at least 8 characters."
  }
  if (lower.includes("unable to validate email")) {
    return "Please enter a valid email address."
  }
  if (lower.includes("email rate limit") || lower.includes("too many requests")) {
    return "Too many attempts. Wait a minute and try again."
  }
  return "We couldn't create your account. Try again or use Google."
}

// Password strength indicator
function getPasswordStrength(password: string): { label: string; color: string } {
  if (password.length < 8) return { label: "Too short", color: "bg-zinc-200" }
  const hasLower = /[a-z]/.test(password)
  const hasUpper = /[A-Z]/.test(password)
  const hasNumber = /[0-9]/.test(password)
  const hasSpecial = /[^a-zA-Z0-9]/.test(password)
  const score = [hasLower, hasUpper, hasNumber, hasSpecial].filter(Boolean).length
  if (password.length >= 12 && score >= 3) return { label: "Strong", color: "bg-emerald-500" }
  if (password.length >= 8 && score >= 2) return { label: "Fair", color: "bg-amber-500" }
  return { label: "Weak", color: "bg-red-400" }
}

export default function GetStartedPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Auth guard: redirect logged-in users based on billing status
  useEffect(() => {
    if (authLoading || !user) return
    
    let cancelled = false
    const checkAccess = async () => {
      try {
        const status = await billingApi.status()
        if (cancelled) return
        
        // canAccessApp means user can enter the app (trialing, active, free with access)
        if ((status as { canAccessApp?: boolean }).canAccessApp) {
          router.replace("/operator")
        } else {
          // User exists but no access - send to billing
          router.replace("/settings/billing?reason=subscription_required")
        }
      } catch {
        // On error, allow through to operator (fail open for new signups)
        if (!cancelled) router.replace("/operator")
      }
    }
    
    void checkAccess()
    return () => { cancelled = true }
  }, [user, authLoading, router])

  // Reset loading state on page show (back/forward navigation)
  useEffect(() => {
    const onPageShow = () => {
      setIsLoading(false)
      setLoadingProvider(null)
    }
    window.addEventListener("pageshow", onPageShow)
    return () => window.removeEventListener("pageshow", onPageShow)
  }, [])

  // OAuth signup - redirects to /operator
  const handleOAuth = async (provider: "google" | "github" | "azure") => {
    setAuthError(null)
    setSuccessMessage(null)
    setLoadingProvider(provider)

    const result = await beginOAuthSignIn(provider, "/operator", true)
    if (!result.ok) {
      setAuthError(humanizeAuthError(result.error))
      setLoadingProvider(null)
    }
    // On success, browser redirects to OAuth provider
  }

  // Email signup - creates account immediately
  const handleEmailSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    setSuccessMessage(null)

    // Validation
    if (!agreedToTerms) {
      setAuthError("Please accept the Terms and Privacy Policy to continue.")
      return
    }
    if (!email.trim() || !password.trim()) {
      setAuthError("Please enter both email and password.")
      return
    }
    if (password.length < 8) {
      setAuthError("Password must be at least 8 characters.")
      return
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email.trim())) {
      setAuthError("Please enter a valid email address.")
      return
    }

    setIsLoading(true)
    try {
      const { data, error } = await supabaseClient.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: getAuthRedirectUrl("/operator", true),
        },
      })

      if (error) throw error

      // Session may exist immediately (confirmations disabled) or require email verify
      const session = data.session ?? (await supabaseClient.auth.getSession()).data.session

      if (!session) {
        // Email confirmation required
        setSuccessMessage("Check your inbox — we sent a confirmation link. Click it to access your workspace.")
        setIsLoading(false)
        return
      }

      // Seed demo data (idempotent)
      try {
        await onboardingApi.bootstrap()
      } catch {
        // Non-blocking — user still gets in
        console.warn("Demo bootstrap failed, continuing to app")
      }

      router.replace("/operator")
    } catch (err) {
      setAuthError(humanizeAuthError(err instanceof Error ? err.message : "Signup failed"))
      setIsLoading(false)
    }
  }

  const passwordStrength = password ? getPasswordStrength(password) : null
  const anyLoading = isLoading || loadingProvider !== null

  return (
    <div className="min-h-screen bg-white relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-50/50 via-white to-white" />
      <div 
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-[420px]"
        >
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900 tracking-tight">
              Build your AI team in minutes
            </h1>
            <p className="mt-3 text-zinc-500">
              Agents that work like employees, integrations they use as tools.
              <br className="hidden sm:block" />
              No credit card required.
            </p>
            <p className="mt-4 text-xs text-zinc-400">
              7-day free trial · Cancel anytime · SOC2-ready infrastructure
            </p>
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl border border-zinc-200/80 shadow-xl shadow-zinc-200/40 p-6 sm:p-8">
            {/* Success message */}
            {successMessage && (
              <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 flex items-start gap-3">
                <Check className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                <span>{successMessage}</span>
              </div>
            )}

            {/* Error message */}
            {authError && (
              <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700" role="alert">
                {authError}
                {authError.includes("already exists") && (
                  <Link href="/login" className="block mt-2 text-red-800 underline font-medium">
                    Sign in instead
                  </Link>
                )}
              </div>
            )}

            {/* OAuth Buttons */}
            <div className="space-y-3">
              {[
                { 
                  id: "google" as const, 
                  icon: (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                  ), 
                  label: "Continue with Google" 
                },
                { 
                  id: "github" as const, 
                  icon: <Github className="h-5 w-5" />, 
                  label: "Continue with GitHub" 
                },
                { 
                  id: "azure" as const, 
                  icon: (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path fill="#F25022" d="M1 1h10v10H1z"/>
                      <path fill="#00A4EF" d="M1 13h10v10H1z"/>
                      <path fill="#7FBA00" d="M13 1h10v10H13z"/>
                      <path fill="#FFB900" d="M13 13h10v10H13z"/>
                    </svg>
                  ), 
                  label: "Continue with Microsoft" 
                },
              ].map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => handleOAuth(provider.id)}
                  disabled={anyLoading}
                  className="w-full flex items-center justify-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 min-h-[48px] text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loadingProvider === provider.id ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      {provider.icon}
                      <span>{provider.label}</span>
                    </>
                  )}
                </button>
              ))}
            </div>

            {/* Divider */}
            <div className="flex items-center gap-4 my-6">
              <div className="h-px flex-1 bg-zinc-200" />
              <span className="text-xs text-zinc-400 uppercase tracking-wide">or continue with email</span>
              <div className="h-px flex-1 bg-zinc-200" />
            </div>

            {/* Email Form */}
            <form onSubmit={handleEmailSignup} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-zinc-700 mb-1.5">
                  Work email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={anyLoading}
                  className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 min-h-[48px] text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 disabled:bg-zinc-50 disabled:cursor-not-allowed"
                  placeholder="you@company.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-zinc-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    disabled={anyLoading}
                    className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 pr-12 min-h-[48px] text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 disabled:bg-zinc-50 disabled:cursor-not-allowed"
                    placeholder="Min 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={anyLoading}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-zinc-600 transition-colors disabled:cursor-not-allowed"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {/* Password strength indicator */}
                {passwordStrength && password.length > 0 && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 h-1 bg-zinc-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all ${passwordStrength.color}`}
                        style={{ width: passwordStrength.label === "Strong" ? "100%" : passwordStrength.label === "Fair" ? "66%" : "33%" }}
                      />
                    </div>
                    <span className="text-xs text-zinc-500">{passwordStrength.label}</span>
                  </div>
                )}
              </div>

              {/* Terms checkbox */}
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  id="terms"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  disabled={anyLoading}
                  className="mt-1 h-4 w-4 rounded border-zinc-300 text-emerald-500 focus:ring-emerald-500/20 disabled:cursor-not-allowed"
                />
                <label htmlFor="terms" className="text-xs text-zinc-500">
                  I agree to the{" "}
                  <Link href="/terms" className="text-emerald-600 hover:text-emerald-700 underline">
                    Terms of Service
                  </Link>
                  {" "}and{" "}
                  <Link href="/privacy" className="text-emerald-600 hover:text-emerald-700 underline">
                    Privacy Policy
                  </Link>
                </label>
              </div>

              {/* Submit button */}
              <button
                type="submit"
                disabled={anyLoading}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 min-h-[48px] text-sm font-medium text-white transition-all hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Creating account...</span>
                  </>
                ) : (
                  <span>Create free account</span>
                )}
              </button>
            </form>
          </div>

          {/* Footer link */}
          <p className="mt-6 text-center text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="text-emerald-600 hover:text-emerald-700 font-medium">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
