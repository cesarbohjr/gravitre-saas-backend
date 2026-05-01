"use client"

import { Suspense, useState, useEffect } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Eye, EyeOff, Loader2, Github, ArrowRight, Shield, Sparkles } from "lucide-react"
import { supabaseClient } from "@/lib/supabaseClient"
import { useAuth } from "@/lib/auth-context"
import { beginOAuthSignIn } from "@/lib/oauth"

const features = [
  "Deploy AI agents in minutes",
  "Automate complex workflows",
  "Scale with enterprise security",
]

function LoginPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, loading: authLoading } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [activeFeature, setActiveFeature] = useState(0)
  const [authError, setAuthError] = useState<string | null>(null)

  // Show session expired message if redirected from middleware
  useEffect(() => {
    if (searchParams.get("session_expired") === "true") {
      setAuthError("Your session has expired. Please sign in again.")
    }
  }, [searchParams])

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveFeature((prev) => (prev + 1) % features.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const resetAuthLoading = () => {
      setIsLoading(false)
      setLoadingProvider(null)
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
    if (!authLoading && user) {
      const redirect = searchParams.get("redirect") || "/operator"
      router.replace(redirect)
    }
  }, [user, authLoading, router, searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    setIsLoading(true)

    const { error } = await supabaseClient.auth.signInWithPassword({
      email,
      password,
    })

    setIsLoading(false)
    if (error) {
      setAuthError(error.message)
      return
    }

    const redirect = searchParams.get("redirect") || "/operator"
    router.push(redirect)
  }

  const handleOAuth = async (provider: string) => {
    setAuthError(null)
    setLoadingProvider(provider)

    const selectedProvider =
      provider === "github" ? "github" : provider === "microsoft" ? "azure" : "google"
    const resetTimer = setTimeout(() => {
      setLoadingProvider(null)
      setAuthError("Sign-in timed out. Please try again.")
    }, 20000)

    const result = await beginOAuthSignIn(selectedProvider, "/operator")
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
    <div className="min-h-screen bg-zinc-50 relative overflow-hidden">
      {/* Background grid */}
      <div 
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)
          `,
          backgroundSize: '48px 48px',
        }}
      />

      {/* Main content - split layout */}
      <div className="relative z-10 min-h-screen flex">
        
        {/* Left side - Branding */}
        <div className="hidden lg:flex lg:w-1/2 flex-col items-center justify-center px-8 xl:px-16 relative">
          {/* Decorative gradient orb */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-br from-emerald-100/40 to-teal-100/30 rounded-full blur-3xl pointer-events-none" />
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-10 flex flex-col items-center text-center"
          >
            <h1 className="text-4xl xl:text-5xl font-bold text-zinc-900 leading-[1.15] tracking-tight">
              Your AI team,
              <br />
              <span className="text-emerald-600">managed simply.</span>
            </h1>
            
            {/* Animated feature text */}
            <div className="mt-6 h-8">
              <AnimatePresence mode="wait">
                <motion.p
                  key={activeFeature}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="text-lg text-zinc-500"
                >
                  {features[activeFeature]}
                </motion.p>
              </AnimatePresence>
            </div>

            {/* Trust indicators */}
            <div className="mt-12 flex items-center gap-6 text-zinc-400">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                <span className="text-sm">Secure by Design</span>
              </div>
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                <span className="text-sm">Enterprise Ready</span>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Right side - Login form */}
        <div className="w-full lg:w-1/2 flex items-center justify-center px-6 py-12">
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="w-full max-w-[440px]"
          >
            <div className="bg-white rounded-2xl border border-zinc-200/80 shadow-xl shadow-zinc-200/40 p-8 lg:p-10">
              {/* Header */}
              <div className="text-center mb-8">
                {/* Mobile logo */}
                <div className="lg:hidden mb-6">
                  <Link href="/">
                    <img 
                      src="/images/gravitre-logo.png" 
                      alt="Gravitre" 
                      className="h-7 mx-auto"
                    />
                  </Link>
                </div>
                <h1 className="text-2xl font-bold text-zinc-900">Sign in</h1>
                <p className="mt-2 text-sm text-zinc-500">
                  Access your AI command center
                </p>
                {authError && (
                  <p className="mt-3 text-sm text-red-600">{authError}</p>
                )}
              </div>

              {/* OAuth buttons */}
              <div className="space-y-3 mb-6">
                {[
                  { id: "google", icon: (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                  ), label: "Continue with Google" },
                  { id: "github", icon: <Github className="h-5 w-5" />, label: "Continue with GitHub" },
                  { id: "microsoft", icon: (
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path fill="#F25022" d="M1 1h10v10H1z"/>
                      <path fill="#00A4EF" d="M1 13h10v10H1z"/>
                      <path fill="#7FBA00" d="M13 1h10v10H13z"/>
                      <path fill="#FFB900" d="M13 13h10v10H13z"/>
                    </svg>
                  ), label: "Continue with Microsoft" },
                ].map((provider) => (
                  <motion.button
                    key={provider.id}
                    onClick={() => handleOAuth(provider.id)}
                    disabled={isLoading || loadingProvider !== null}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    className="w-full flex items-center justify-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50"
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
                <div className="h-px flex-1 bg-zinc-200" />
                <span className="text-xs text-zinc-400 uppercase tracking-wide">or</span>
                <div className="h-px flex-1 bg-zinc-200" />
              </div>

              {/* Email form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-zinc-700">
                      Password
                    </label>
                    <Link 
                      href="/forgot-password" 
                      className="text-xs text-emerald-600 hover:text-emerald-700 transition-colors"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      required
                      className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 pr-12 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-zinc-600 transition-colors"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <motion.button
                  type="submit"
                  disabled={isLoading || loadingProvider !== null}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-zinc-800 disabled:opacity-50"
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
              <p className="mt-6 text-center text-sm text-zinc-500">
                {"Don't have an account? "}
                <Link href="/get-started" className="text-emerald-600 hover:text-emerald-700 transition-colors font-medium">
                  Get started free
                </Link>
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

function LoginPageFallback() {
  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
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
