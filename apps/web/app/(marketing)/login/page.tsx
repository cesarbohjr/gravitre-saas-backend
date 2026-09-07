"use client"

import { Suspense, useState, useEffect, useRef } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { Eye, EyeOff, Loader2, Github, ArrowRight } from "lucide-react"
import { supabaseClient } from "@/lib/supabaseClient"
import { useAuth } from "@/lib/auth-context"
import { beginOAuthSignIn } from "@/lib/oauth"
import { clearAuthTransition, markAuthTransition } from "@/lib/auth-transition"
import { APP_ROUTES } from "@/lib/app-routes"
import { getAuthRedirectUrl } from "@/lib/auth-redirect"
import { GravitreMarketingLogo } from "@/components/marketing/gravitre-marketing-logo"
import { GoogleOAuthIcon, MicrosoftOAuthIcon } from "@/components/marketing/oauth-provider-icons"
import { AuthIllustration } from "@/components/marketing/nodus/auth-illustration"
import { Container } from "@/components/marketing/nodus/container"
import { Heading } from "@/components/marketing/nodus/heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"

function LoginPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, loading: authLoading } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const [authInfo, setAuthInfo] = useState<string | null>(null)
  const [showSignupCta, setShowSignupCta] = useState(false)
  const [canResendVerification, setCanResendVerification] = useState(false)
  const [isResendingVerification, setIsResendingVerification] = useState(false)
  const oauthLoginCheckRef = useRef(false)

  const sessionExpiredMessage =
    searchParams.get("session_expired") === "true" ||
    searchParams.get("error") === "session_expired"
      ? "Your session has expired. Please sign in again."
      : null
  const displayedAuthError = authError ?? sessionExpiredMessage

  useEffect(() => {
    // Clear stale Supabase cookies when redirected with an auth error (breaks OAuth loops).
    const error = searchParams.get("error")
    if (
      !error ||
      !["session_expired", "auth_callback_failed", "oauth_error"].includes(error)
    ) {
      return
    }

    let cancelled = false
    const resetBrokenSession = async () => {
      if (error === "session_expired") {
        const { data: { user: liveUser } } = await supabaseClient.auth.getUser()
        if (liveUser && !cancelled) {
          clearAuthTransition()
          window.sessionStorage.removeItem("gravitre_auth_login_redirect")
          await supabaseClient.auth.refreshSession()
          const redirect = searchParams.get("redirect") || APP_ROUTES.home
          router.replace(redirect)
          return
        }
      }

      try {
        await supabaseClient.auth.signOut({ scope: "local" })
      } catch {
        // ignore — cookies may already be invalid
      }
      if (cancelled) return
      window.sessionStorage.removeItem("gravitre_auth_redirecting")
      window.sessionStorage.removeItem("gravitre_auth_login_redirect")
      window.sessionStorage.removeItem("gravitre_auth_redirect_until")
    }

    void resetBrokenSession()
    return () => {
      cancelled = true
    }
  }, [searchParams, router])

  useEffect(() => {
    const resetAuthLoading = () => {
      setIsLoading(false)
      setLoadingProvider(null)
      clearAuthTransition()
    }

    const onPageShow = () => {
      resetAuthLoading()
    }

    window.addEventListener("pageshow", onPageShow)
    return () => {
      window.removeEventListener("pageshow", onPageShow)
    }
  }, [])

  // Redirect to operator if already logged in
  useEffect(() => {
    if (authLoading) return
    if (!user) {
      oauthLoginCheckRef.current = false
      return
    }

    const intent = searchParams.get("intent")
    // Preserve direct `/login` navigation (e.g. header Log in click) instead of
    // auto-bouncing to app routes, which can cascade to `/get-started`.
    // Only run post-auth redirect logic for explicit login intent flows.
    if (intent !== "login") {
      return
    }

    if (oauthLoginCheckRef.current) return
    oauthLoginCheckRef.current = true

    const verifyExistingAccount = async () => {
      try {
        const { data } = await supabaseClient.auth.getSession()
        const token = data.session?.access_token
        if (!token) {
          throw new Error("No active session found")
        }

        const response = await fetch("/api/auth/me", {
          headers: {
            Authorization: `Bearer ${token}`,
            accept: "application/json",
          },
          cache: "no-store",
        })

        if (!response.ok) {
          throw new Error("Unable to verify account")
        }

        const payload = await response.json()
        const hasExistingAccount = Boolean(payload?.user?.created_at)
        if (!hasExistingAccount) {
          await supabaseClient.auth.signOut()
          setShowSignupCta(true)
          setAuthError("Your account doesn't exist yet. Sign up to continue.")
          return
        }

        const redirect = searchParams.get("redirect") || APP_ROUTES.home
        markAuthTransition()
        router.replace(redirect)
      } catch {
        await supabaseClient.auth.signOut()
        setShowSignupCta(true)
        setAuthError("We couldn't verify your account. Sign up to continue.")
      }
    }

    void verifyExistingAccount()
  }, [user, authLoading, router, searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    setAuthInfo(null)
    setCanResendVerification(false)
    setIsLoading(true)

    const { error } = await supabaseClient.auth.signInWithPassword({
      email,
      password,
    })

    setIsLoading(false)
    if (error) {
      const message = (error.message || "").toLowerCase()
      if (message.includes("invalid login credentials") || message.includes("invalid_credentials")) {
        setAuthError(
          "Invalid email or password. If you originally signed in with Google or Microsoft, use those buttons — password sign-in only works for email/password accounts."
        )
      } else if (message.includes("email not confirmed")) {
        setAuthError(error.message)
        setCanResendVerification(true)
      } else {
        setAuthError(error.message)
      }
      return
    }

    const redirect = searchParams.get("redirect") || APP_ROUTES.home
    markAuthTransition()
    router.push(redirect)
  }

  const handleResendVerification = async () => {
    if (!email.trim()) {
      setAuthError("Enter your email first so we can resend verification.")
      return
    }
    setAuthError(null)
    setAuthInfo(null)
    setIsResendingVerification(true)
    try {
      const { error } = await supabaseClient.auth.resend({
        type: "signup",
        email: email.trim(),
        options: {
          emailRedirectTo: getAuthRedirectUrl(APP_ROUTES.home),
        },
      })
      if (error) {
        setAuthError(error.message)
        return
      }
      setAuthInfo("Verification email sent. Open the link, then sign in.")
      setCanResendVerification(false)
    } finally {
      setIsResendingVerification(false)
    }
  }

  const handleOAuth = async (provider: string) => {
    setAuthError(null)
    setShowSignupCta(false)
    setLoadingProvider(provider)

    const selectedProvider =
      provider === "github" ? "github" : provider === "microsoft" ? "azure" : "google"

    const resetTimer = setTimeout(() => {
      setLoadingProvider(null)
      setAuthError("Sign-in timed out. Please try again.")
    }, 20000)

    const result = await beginOAuthSignIn(selectedProvider, APP_ROUTES.home)
    if (!result.ok) {
      clearTimeout(resetTimer)
      setAuthError(result.error)
      setLoadingProvider(null)
      return
    }
    clearTimeout(resetTimer)
  }

  // Don't block render - show form immediately, redirect happens via useEffect if logged in
  return (
    <div className="min-h-screen bg-white">
      <Container className="border-divide min-h-screen border-x py-10 md:py-16">
        <div className="grid grid-cols-1 gap-10 px-4 md:grid-cols-2 md:px-8 lg:gap-16">
          <div className="hidden md:block">
            <AuthIllustration />
          </div>

          <div className="flex w-full items-center justify-center">
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="w-full max-w-[440px]"
          >
            <div className="shadow-aceternity rounded-2xl border border-divide bg-white p-6 sm:p-8 lg:p-10">
              <div className="mb-8 text-left">
                <div className="mb-6 md:hidden">
                  <GravitreMarketingLogo height={40} className="h-10" />
                </div>
                <Heading className="text-left text-3xl lg:text-4xl">Welcome back</Heading>
                <SubHeading as="p" className="mt-2 text-left">
                  Sign in to your Gravitre workspace
                </SubHeading>
                {displayedAuthError && (
                  <div className="mt-3 space-y-2">
                    <p className="text-sm text-red-600">{displayedAuthError}</p>
                    {canResendVerification && (
                      <button
                        type="button"
                        onClick={handleResendVerification}
                        disabled={isResendingVerification}
                        className="inline-block text-sm font-medium text-brand transition-colors disabled:opacity-50"
                      >
                        {isResendingVerification ? "Sending..." : "Resend verification email"}
                      </button>
                    )}
                    {showSignupCta && (
                      <Link
                        href="/get-started"
                        className="text-brand inline-block text-sm font-medium transition-colors"
                      >
                        Sign up here
                      </Link>
                    )}
                  </div>
                )}
                {authInfo && <p className="text-brand mt-3 text-sm">{authInfo}</p>}
              </div>

              {/* OAuth buttons */}
              <div className="space-y-3 mb-6">
                {[
                  { id: "google", icon: <GoogleOAuthIcon />, label: "Continue with Google" },
                  { id: "github", icon: <Github className="h-5 w-5" />, label: "Continue with GitHub" },
                  { id: "microsoft", icon: <MicrosoftOAuthIcon />, label: "Continue with Microsoft" },
                ].map((provider) => (
                  <motion.button
                    key={provider.id}
                    onClick={() => handleOAuth(provider.id)}
                    disabled={isLoading || loadingProvider !== null}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    className="w-full flex items-center justify-center gap-3 rounded-xl border border-border bg-card px-4 py-3 min-h-[48px] text-sm font-medium text-foreground transition-all hover:bg-muted/50 hover:border-border disabled:opacity-50"
                  >
                    {loadingProvider === provider.id ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        {provider.icon}
                        <span>{provider.label}</span>
                      </>
                    )}
                  </motion.button>
                ))}
              </div>

              {/* Divider */}
              <div className="flex items-center gap-4 mb-6">
                <div className="h-px flex-1 bg-muted" />
                <span className="text-xs text-muted-foreground uppercase tracking-wide">or</span>
                <div className="h-px flex-1 bg-muted" />
              </div>

              {/* Email form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    className="w-full rounded-xl border border-border bg-card px-4 py-3 min-h-[48px] text-sm text-foreground placeholder:text-muted-foreground transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-foreground">
                      Password
                    </label>
                    <Link 
                      href="/forgot-password" 
                      className="text-xs text-primary hover:text-primary transition-colors"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      required
                      className="w-full rounded-xl border border-border bg-card px-4 py-3 pr-12 min-h-[48px] text-sm text-foreground placeholder:text-muted-foreground transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-muted-foreground hover:text-muted-foreground transition-colors"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    Use Google or Microsoft above if you signed up with SSO — password login is for email accounts only.
                  </p>
                </div>

                <motion.button
                  type="submit"
                  disabled={isLoading || loadingProvider !== null}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 min-h-[48px] text-sm font-semibold text-white transition-all hover:bg-foreground/90 disabled:opacity-50"
                >
                  {isLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <span>Sign in</span>
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </motion.button>
              </form>

              {/* Sign up link */}
              <p className="mt-6 text-center text-sm text-muted-foreground">
                {"Don't have an account? "}
                <Link href="/get-started" className="text-primary hover:text-primary transition-colors font-medium">
                  Get started free
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
            </div>
          </motion.div>
          </div>
        </div>
      </Container>
    </div>
  )
}

function LoginPageFallback() {
  return (
    <div className="min-h-screen bg-muted/50 flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageFallback />}>
      <LoginPageContent />
    </Suspense>
  )
}
