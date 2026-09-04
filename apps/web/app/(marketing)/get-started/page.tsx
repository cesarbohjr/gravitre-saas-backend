"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Eye, EyeOff, Loader2, Github, Check } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { beginOAuthSignIn } from "@/lib/oauth"
import { onboardingApi, billingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { getAuthRedirectUrl } from "@/lib/auth-redirect"
import { supabaseClient } from "@/lib/supabaseClient"
import { GoogleOAuthIcon, MicrosoftOAuthIcon } from "@/components/marketing/oauth-provider-icons"

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
  if (password.length < 8) return { label: "Too short", color: "bg-muted" }
  const hasLower = /[a-z]/.test(password)
  const hasUpper = /[A-Z]/.test(password)
  const hasNumber = /[0-9]/.test(password)
  const hasSpecial = /[^a-zA-Z0-9]/.test(password)
  const score = [hasLower, hasUpper, hasNumber, hasSpecial].filter(Boolean).length
  if (password.length >= 12 && score >= 3) return { label: "Strong", color: "bg-primary/100" }
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
          router.replace(APP_ROUTES.welcome)
        } else {
          // User exists but no access - send to billing
          router.replace("/settings/billing?reason=subscription_required")
        }
      } catch {
        // On error, allow through to welcome (fail open for new signups)
        if (!cancelled) router.replace(APP_ROUTES.welcome)
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

  // OAuth signup - redirects to Command Center
  const handleOAuth = async (provider: "google" | "github" | "azure") => {
    setAuthError(null)
    setSuccessMessage(null)
    setLoadingProvider(provider)

    const result = await beginOAuthSignIn(provider, APP_ROUTES.welcome, true)
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
          emailRedirectTo: getAuthRedirectUrl(APP_ROUTES.welcome, true),
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

      router.replace(APP_ROUTES.welcome)
    } catch (err) {
      setAuthError(humanizeAuthError(err instanceof Error ? err.message : "Signup failed"))
      setIsLoading(false)
    }
  }

  const passwordStrength = password ? getPasswordStrength(password) : null
  const anyLoading = isLoading || loadingProvider !== null

  return (
    <div className="min-h-screen bg-card relative overflow-x-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/10/50 via-white to-white" />
      <div 
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
        }}
      />

      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 py-6 sm:py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-[420px]"
        >
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">
              Build your AI team in minutes
            </h1>
            <p className="mt-3 text-muted-foreground">
              Agents that work like employees, integrations they use as tools.
              <br className="hidden sm:block" />
              No credit card required.
            </p>
            <p className="mt-4 text-xs text-muted-foreground">
              7-day free trial · Cancel anytime · Encrypted by default
            </p>
          </div>

          {/* Card */}
          <div className="bg-card rounded-2xl border border-border/80 shadow-xl shadow-border/40 p-6 sm:p-8">
            {/* Success message */}
            {successMessage && (
              <div className="mb-6 p-4 rounded-xl bg-primary/10 border border-primary/20 text-sm text-primary flex items-start gap-3">
                <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
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
                  icon: <GoogleOAuthIcon />,
                  label: "Continue with Google",
                },
                {
                  id: "github" as const,
                  icon: <Github className="h-5 w-5" />,
                  label: "Continue with GitHub",
                },
                {
                  id: "azure" as const,
                  icon: <MicrosoftOAuthIcon />,
                  label: "Continue with Microsoft",
                },
              ].map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => handleOAuth(provider.id)}
                  disabled={anyLoading}
                  className="w-full flex items-center justify-center gap-3 rounded-xl border border-border bg-card px-4 py-3 min-h-[48px] text-sm font-medium text-foreground transition-all hover:bg-muted/50 hover:border-border disabled:opacity-50 disabled:cursor-not-allowed"
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
              <div className="h-px flex-1 bg-muted" />
              <span className="text-xs text-muted-foreground uppercase tracking-wide">or continue with email</span>
              <div className="h-px flex-1 bg-muted" />
            </div>

            {/* Email Form */}
            <form onSubmit={handleEmailSignup} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1.5">
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
                  className="w-full rounded-xl border border-border bg-card px-4 py-3 min-h-[48px] text-sm text-foreground placeholder:text-muted-foreground transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:bg-muted/50 disabled:cursor-not-allowed"
                  placeholder="you@company.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1.5">
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
                    className="w-full rounded-xl border border-border bg-card px-4 py-3 pr-12 min-h-[48px] text-sm text-foreground placeholder:text-muted-foreground transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:bg-muted/50 disabled:cursor-not-allowed"
                    placeholder="Min 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={anyLoading}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-muted-foreground transition-colors disabled:cursor-not-allowed"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {/* Password strength indicator */}
                {passwordStrength && password.length > 0 && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all ${passwordStrength.color}`}
                        style={{ width: passwordStrength.label === "Strong" ? "100%" : passwordStrength.label === "Fair" ? "66%" : "33%" }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{passwordStrength.label}</span>
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
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary/20 disabled:cursor-not-allowed"
                />
                <label htmlFor="terms" className="text-xs text-muted-foreground">
                  I agree to the{" "}
                  <Link href="/terms" className="text-primary hover:text-primary underline">
                    Terms of Service
                  </Link>
                  {" "}and{" "}
                  <Link href="/privacy" className="text-primary hover:text-primary underline">
                    Privacy Policy
                  </Link>
                </label>
              </div>

              {/* Submit button */}
              <button
                type="submit"
                disabled={anyLoading}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 min-h-[48px] text-sm font-medium text-white transition-all hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed"
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
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-primary hover:text-primary font-medium">
              Sign in
            </Link>
          </p>
          
          {/* Legal footer */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
            <Link href="/privacy" className="hover:text-muted-foreground transition-colors">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-muted-foreground transition-colors">
              Terms
            </Link>
            <Link href="/security" className="hover:text-muted-foreground transition-colors">
              Security
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
