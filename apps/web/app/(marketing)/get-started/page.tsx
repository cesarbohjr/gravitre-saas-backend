"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { 
  ArrowRight, 
  ArrowLeft,
  Eye, 
  EyeOff, 
  Loader2, 
  Github, 
  Check,
  Building2,
  Users,
  Zap,
  Shield,
  Sparkles,
  Rocket
} from "lucide-react"
import { getAuthRedirectUrl } from "@/lib/auth-redirect"
import { supabaseClient } from "@/lib/supabaseClient"
import { useAuth } from "@/lib/auth-context"
import { beginOAuthSignIn } from "@/lib/oauth"
import { billingApi } from "@/lib/api"

const plans = [
  {
    id: "starter",
    name: "Starter",
    price: "$79",
    period: "/month",
    description: "Perfect for small teams getting started",
    features: ["5 AI agents", "1,000 runs/month", "Email support", "Basic analytics"],
    popular: false,
  },
  {
    id: "growth",
    name: "Growth",
    price: "$299",
    period: "/month",
    description: "For growing teams that need more power",
    features: ["25 AI agents", "10,000 runs/month", "Priority support", "Advanced analytics", "Custom integrations"],
    popular: true,
  },
  {
    id: "scale",
    name: "Scale",
    price: "$999",
    period: "/month",
    description: "Enterprise-grade for large organizations",
    features: ["Unlimited agents", "Unlimited runs", "Dedicated CSM", "SSO & SAML", "SLA guarantee"],
    popular: false,
  },
]

const useCases = [
  { id: "sales", label: "Sales & CRM", icon: Users },
  { id: "marketing", label: "Marketing", icon: Sparkles },
  { id: "data", label: "Analytics", icon: Zap },
  { id: "finance", label: "Finance", icon: Building2 },
  { id: "support", label: "Support", icon: Shield },
]

const stepTitles = [
  { num: 1, title: "Create account" },
  { num: 2, title: "Your workspace" },
  { num: 3, title: "Select plan" },
  { num: 4, title: "Ready to go" },
]

export default function GetStartedPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [selectedPlan, setSelectedPlan] = useState("growth")
  const [selectedUseCases, setSelectedUseCases] = useState<string[]>([])
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const [billingError, setBillingError] = useState<string | null>(null)
  const [isCheckingBilling, setIsCheckingBilling] = useState(false)

  // Redirect only after paid checkout is active
  useEffect(() => {
    if (authLoading || !user) return

    const intent =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("intent")
        : null

    if (intent === "signup") {
      setStep((current) => (current < 2 ? 2 : current))
      return
    }

    let cancelled = false
    const checkBilling = async () => {
      setIsCheckingBilling(true)
      try {
        const status = await billingApi.status()
        if (cancelled) return
        if (status.billingStatus === "active") {
          router.replace("/operator")
          return
        }
        setStep((current) => (current < 3 ? 3 : current))
        setBillingError("Complete checkout to continue to your operator dashboard.")
      } catch {
        if (!cancelled) {
          setStep((current) => (current < 3 ? 3 : current))
          setBillingError("We could not verify billing yet. Please complete checkout and try again.")
        }
      } finally {
        if (!cancelled) {
          setIsCheckingBilling(false)
        }
      }
    }

    void checkBilling()
    return () => {
      cancelled = true
    }
  }, [user, authLoading, router])

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

  const handleOAuth = async (provider: string) => {
    setAuthError(null)
    setLoadingProvider(provider)

    const selectedProvider =
      provider === "github" ? "github" : provider === "microsoft" ? "azure" : "google"

    const resetTimer = setTimeout(() => {
      setLoadingProvider(null)
      setAuthError("Sign-in timed out. Please try again.")
    }, 20000)

    const result = await beginOAuthSignIn(selectedProvider, "/get-started?oauth=1&intent=signup")
    if (!result.ok) {
      clearTimeout(resetTimer)
      setAuthError(result.error)
      setLoadingProvider(null)
      return
    }
    clearTimeout(resetTimer)
  }

  const handleEmailSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    setIsLoading(true)

    const { error } = await supabaseClient.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: getAuthRedirectUrl("/operator"),
      },
    })

    setIsLoading(false)
    
    if (error) {
      setAuthError(error.message)
      return
    }

    setStep(2)
  }

  const handleCompanySetup = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 800))
    setStep(3)
    setIsLoading(false)
  }

  const handlePlanSelect = () => {
    setBillingError(null)
    setIsCheckingBilling(true)
    void (async () => {
      try {
        const response = await billingApi.createCheckoutForPlan(selectedPlan)
        if (response.checkout_url) {
          window.location.assign(response.checkout_url)
          return
        }
        setBillingError("Unable to start checkout. Please try again.")
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to start checkout."
        setBillingError(message)
      } finally {
        setIsCheckingBilling(false)
      }
    })()
  }

  const handleComplete = async () => {
    setBillingError(null)
    setIsLoading(true)
    try {
      const status = await billingApi.status()
      if (status.billingStatus !== "active") {
        setBillingError("Payment is still pending. Finish checkout, then try again.")
        setStep(3)
        return
      }
      router.push("/operator")
    } catch {
      setBillingError("We could not verify billing yet. Please try again in a moment.")
      setStep(3)
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerifyPayment = async () => {
    setBillingError(null)
    setIsCheckingBilling(true)
    try {
      const status = await billingApi.status()
      if (status.billingStatus !== "active") {
        setBillingError("Payment not confirmed yet. Complete checkout and click verify again.")
        return
      }
      setStep(4)
    } catch {
      setBillingError("We could not verify billing yet. Please try again.")
    } finally {
      setIsCheckingBilling(false)
    }
  }

  const toggleUseCase = (id: string) => {
    setSelectedUseCases(prev => 
      prev.includes(id) ? prev.filter(u => u !== id) : [...prev, id]
    )
  }

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

      {/* Decorative gradient orb */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-br from-emerald-100/60 to-teal-100/40 rounded-full blur-3xl pointer-events-none" />

      {/* Step indicator */}
      <div className="relative z-10 py-6 sm:py-8 overflow-x-auto">
        <div className="flex items-center justify-start sm:justify-center gap-0 px-4 min-w-max mx-auto">
          {stepTitles.map((s, i) => (
            <div key={i} className="flex items-center">
              <button
                onClick={() => i + 1 < step && setStep(i + 1)}
                disabled={i + 1 > step}
                className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-full text-xs sm:text-sm font-medium transition-all whitespace-nowrap ${
                  i + 1 === step 
                    ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/25" 
                    : i + 1 < step 
                      ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 cursor-pointer" 
                      : "bg-zinc-100 text-zinc-400"
                }`}
              >
                {i + 1 < step ? (
                  <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                ) : (
                  <span className={`h-4 w-4 sm:h-5 sm:w-5 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-bold ${
                    i + 1 === step ? "bg-white/20" : "bg-current/10"
                  }`}>
                    {s.num}
                  </span>
                )}
                <span className="hidden sm:inline">{s.title}</span>
                <span className="sm:hidden">{s.num}</span>
              </button>
              {i < stepTitles.length - 1 && (
                <div className={`w-4 sm:w-8 h-0.5 mx-0.5 sm:mx-1 ${i + 1 < step ? "bg-emerald-300" : "bg-zinc-200"}`} />
              )}
            </div>
          ))}
        </div>
      </div>
      
      {/* Main content */}
      <div className="relative z-10 flex items-start justify-center px-4 pb-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-[480px]"
        >
          {/* Card */}
          <div className="bg-white rounded-2xl border border-zinc-200/80 shadow-xl shadow-zinc-200/40 overflow-hidden">
            <AnimatePresence mode="wait">
              {/* Step 1: Account Creation */}
              {step === 1 && (
                <motion.div
                  key="step1"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="p-8"
                >
                  <div className="text-center mb-8">
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 200 }}
                      className="mb-4 inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/25"
                    >
                      <Rocket className="h-7 w-7 text-white" />
                    </motion.div>
                    <h1 className="text-2xl font-bold text-zinc-900">Start your journey</h1>
                    <p className="mt-2 text-sm text-zinc-500">
                      7-day free trial to explore all features.
                    </p>
                    {authError && (
                      <p className="mt-3 text-sm text-red-600">{authError}</p>
                    )}
                  </div>

                  {/* OAuth Buttons - All 3 providers */}
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

                  <form onSubmit={handleEmailSignup} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                        Work email
                      </label>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="you@company.com"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                        Password
                      </label>
                      <div className="relative">
                        <input
                          type={showPassword ? "text" : "password"}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                          minLength={8}
                          className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 pr-12 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                          placeholder="Min 8 characters"
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

                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        id="terms"
                        checked={agreedToTerms}
                        onChange={(e) => setAgreedToTerms(e.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-zinc-300 text-emerald-500 focus:ring-emerald-500/20"
                      />
                      <label htmlFor="terms" className="text-xs text-zinc-500">
                        I agree to the{" "}
                        <Link href="/terms" className="text-emerald-600 hover:text-emerald-700">Terms</Link>
                        {" "}and{" "}
                        <Link href="/privacy" className="text-emerald-600 hover:text-emerald-700">Privacy Policy</Link>
                      </label>
                    </div>

                    <motion.button
                      type="submit"
                      disabled={isLoading || !agreedToTerms}
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {isLoading ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <>
                          <span>Create account</span>
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </motion.button>
                  </form>
                </motion.div>
              )}

              {/* Step 2: Company Setup */}
              {step === 2 && (
                <motion.div
                  key="step2"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="p-8"
                >
                  <button
                    onClick={() => setStep(1)}
                    className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 mb-6 transition-colors"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </button>

                  <h1 className="text-2xl font-bold text-zinc-900">Set up your workspace</h1>
                  <p className="mt-2 text-sm text-zinc-500 mb-8">
                    Tell us a bit about your team
                  </p>

                  <form onSubmit={handleCompanySetup} className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                        Company name
                      </label>
                      <input
                        type="text"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        required
                        className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder:text-zinc-400 transition-all focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="Acme Inc"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-3">
                        What will you use Gravitre for?
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {useCases.map((useCase) => {
                          const Icon = useCase.icon
                          const isSelected = selectedUseCases.includes(useCase.id)
                          return (
                            <button
                              key={useCase.id}
                              type="button"
                              onClick={() => toggleUseCase(useCase.id)}
                              className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm transition-all ${
                                isSelected
                                  ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                                  : "bg-zinc-100 text-zinc-600 border border-zinc-200 hover:border-zinc-300"
                              }`}
                            >
                              <Icon className="h-4 w-4" />
                              {useCase.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <motion.button
                      type="submit"
                      disabled={isLoading || !companyName}
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {isLoading ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <>
                          <span>Continue</span>
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </motion.button>
                  </form>
                </motion.div>
              )}

              {/* Step 3: Plan Selection */}
              {step === 3 && (
                <motion.div
                  key="step3"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="p-8"
                >
                  <button
                    onClick={() => setStep(2)}
                    className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 mb-6 transition-colors"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </button>

                  <h1 className="text-2xl font-bold text-zinc-900">Choose your plan</h1>
                  <p className="mt-2 text-sm text-zinc-500 mb-6">
                    Start with a 7-day free trial. Cancel anytime.
                  </p>
                  {billingError && (
                    <p className="mb-4 text-sm text-red-600">{billingError}</p>
                  )}

                  <div className="space-y-3">
                    {plans.map((plan) => (
                      <button
                        key={plan.id}
                        onClick={() => setSelectedPlan(plan.id)}
                        className={`w-full text-left rounded-xl p-4 border-2 transition-all ${
                          selectedPlan === plan.id
                            ? "border-emerald-500 bg-emerald-50/50"
                            : "border-zinc-200 hover:border-zinc-300 bg-white"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-zinc-900">{plan.name}</span>
                              {plan.popular && (
                                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs font-medium">
                                  Popular
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-zinc-500 mt-1">{plan.description}</p>
                          </div>
                          <div className="text-right">
                            <span className="text-xl font-bold text-zinc-900">{plan.price}</span>
                            <span className="text-sm text-zinc-500">{plan.period}</span>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {plan.features.map((feature, i) => (
                            <span key={i} className="inline-flex items-center gap-1 text-xs text-zinc-600">
                              <Check className="h-3 w-3 text-emerald-500" />
                              {feature}
                            </span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>

                  <motion.button
                    onClick={handlePlanSelect}
                    disabled={isCheckingBilling}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    className="w-full mt-6 flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-zinc-800 disabled:opacity-50"
                  >
                    {isCheckingBilling ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <span>Continue to Payment</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </motion.button>
                  <button
                    type="button"
                    onClick={handleVerifyPayment}
                    disabled={isCheckingBilling}
                    className="w-full mt-3 rounded-xl border border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 disabled:opacity-50"
                  >
                    I&apos;ve completed payment
                  </button>
                </motion.div>
              )}

              {/* Step 4: Ready */}
              {step === 4 && (
                <motion.div
                  key="step4"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="p-8 text-center"
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
                    className="mb-6 inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/25"
                  >
                    <Rocket className="h-8 w-8 text-white" />
                  </motion.div>

                  <motion.h1 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-2xl font-bold text-zinc-900"
                  >
                    You&apos;re all set!
                  </motion.h1>
                  <motion.p 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="mt-2 text-sm text-zinc-500 mb-8"
                  >
                    Your workspace is ready. Let&apos;s build something amazing.
                  </motion.p>

                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="bg-zinc-50 rounded-xl p-4 mb-6 text-left"
                  >
                    <h3 className="font-medium text-zinc-900 mb-3">Your setup:</h3>
                    <div className="space-y-2 text-sm text-zinc-600">
                      <div className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-emerald-500" />
                        <span>Workspace: <strong className="text-zinc-900">{companyName || "Your Company"}</strong></span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-emerald-500" />
                        <span>Plan: <strong className="text-zinc-900">{plans.find(p => p.id === selectedPlan)?.name}</strong> (7-day trial)</span>
                      </div>
                      {selectedUseCases.length > 0 && (
                        <div className="flex items-center gap-2">
                          <Check className="h-4 w-4 text-emerald-500" />
                          <span>Focus: <strong className="text-zinc-900">{selectedUseCases.map(id => useCases.find(u => u.id === id)?.label).join(", ")}</strong></span>
                        </div>
                      )}
                    </div>
                  </motion.div>

                  <motion.button
                    onClick={handleComplete}
                    disabled={isLoading || isCheckingBilling}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600 shadow-lg shadow-emerald-500/25"
                  >
                    {isLoading || isCheckingBilling ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        <span>Launch Dashboard</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Sign in link */}
          <p className="mt-6 text-center text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="text-emerald-600 hover:text-emerald-700 transition-colors font-medium">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
