"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Eye, EyeOff, Loader2, Github, ArrowRight, Shield, Lock, KeyRound } from "lucide-react"

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    router.push("/operator")
  }

  const handleOAuth = async (provider: string) => {
    setLoadingProvider(provider)
    await new Promise(resolve => setTimeout(resolve, 1500))
    router.push("/operator")
  }

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-zinc-100 via-white to-emerald-50/30">
      {/* Subtle pattern overlay */}
      <div 
        className="absolute inset-0 opacity-[0.4]"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgb(0 0 0 / 0.03) 1px, transparent 0)`,
          backgroundSize: '32px 32px',
        }}
      />
      
      {/* Decorative shapes */}
      <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-gradient-to-bl from-emerald-100/50 to-transparent rounded-full blur-3xl translate-x-1/4 -translate-y-1/4" />
      <div className="absolute bottom-0 left-0 w-1/3 h-1/3 bg-gradient-to-tr from-blue-100/30 to-transparent rounded-full blur-3xl -translate-x-1/4 translate-y-1/4" />
      
      {/* Top navigation */}
      <div className="relative z-20 flex items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <img 
            src="/images/gravitre-logo.png" 
            alt="Gravitre" 
            className="h-6"
          />
        </Link>
        <Link 
          href="/get-started" 
          className="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 transition-colors group"
        >
          Create account
          <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </div>
      
      {/* Main content - centered */}
      <div className="relative z-10 flex items-center justify-center min-h-[calc(100vh-72px)] px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Card */}
          <div className="bg-white rounded-2xl border border-zinc-200/80 shadow-xl shadow-zinc-200/50 overflow-hidden">
            {/* Header with icon */}
            <div className="px-8 pt-8 pb-6 text-center border-b border-zinc-100">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className="mb-4 inline-flex items-center justify-center h-12 w-12 rounded-xl bg-zinc-900 shadow-lg"
              >
                <KeyRound className="h-6 w-6 text-white" />
              </motion.div>
              <h1 className="text-xl font-bold text-zinc-900">Welcome back</h1>
              <p className="mt-1 text-sm text-zinc-500">
                Sign in to your command center
              </p>
            </div>

            <div className="p-8">
              {/* OAuth buttons - horizontal layout */}
              <div className="flex gap-3 mb-6">
                <button
                  onClick={() => handleOAuth("google")}
                  disabled={isLoading || loadingProvider !== null}
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50"
                >
                  {loadingProvider === "google" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <svg className="h-5 w-5" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                      </svg>
                      <span className="hidden sm:inline">Google</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => handleOAuth("github")}
                  disabled={isLoading || loadingProvider !== null}
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50"
                >
                  {loadingProvider === "github" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <Github className="h-5 w-5" />
                      <span className="hidden sm:inline">GitHub</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => handleOAuth("microsoft")}
                  disabled={isLoading || loadingProvider !== null}
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50"
                >
                  {loadingProvider === "microsoft" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <svg className="h-5 w-5" viewBox="0 0 24 24">
                        <path fill="#F25022" d="M1 1h10v10H1z"/>
                        <path fill="#00A4EF" d="M1 13h10v10H1z"/>
                        <path fill="#7FBA00" d="M13 1h10v10H13z"/>
                        <path fill="#FFB900" d="M13 13h10v10H13z"/>
                      </svg>
                      <span className="hidden sm:inline">Microsoft</span>
                    </>
                  )}
                </button>
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
                    className="w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:bg-white focus:border-zinc-400 focus:ring-2 focus:ring-zinc-200"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-zinc-700">
                      Password
                    </label>
                    <Link 
                      href="/forgot-password" 
                      className="text-xs text-zinc-500 hover:text-zinc-900 transition-colors"
                    >
                      Forgot?
                    </Link>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      required
                      className="w-full rounded-xl border border-zinc-200 bg-zinc-50/50 px-4 py-2.5 pr-10 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:bg-white focus:border-zinc-400 focus:ring-2 focus:ring-zinc-200"
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

                <button
                  type="submit"
                  disabled={isLoading || loadingProvider !== null}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-zinc-800 disabled:opacity-50"
                >
                  {isLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <span>Sign in</span>
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>

          {/* Sign up link */}
          <p className="mt-6 text-center text-sm text-zinc-500">
            {"New to Gravitre? "}
            <Link href="/get-started" className="text-zinc-900 hover:underline transition-colors font-medium">
              Start your free trial
            </Link>
          </p>

          {/* Trust badges */}
          <div className="flex items-center justify-center gap-6 mt-6 text-zinc-400">
            <div className="flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5" />
              <span className="text-xs">SOC 2 Type II</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5" />
              <span className="text-xs">256-bit SSL</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
