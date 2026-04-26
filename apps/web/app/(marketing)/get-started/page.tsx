"use client"

import { useState } from "react"
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
  Bot,
  Workflow
} from "lucide-react"

const plans = [
  {
    id: "starter",
    name: "Starter",
    price: "$79",
    description: "Perfect for small teams getting started",
    features: ["Up to 5 agents", "1,000 runs/month", "Email support"],
    popular: false,
  },
  {
    id: "growth",
    name: "Growth",
    price: "$299",
    description: "For growing teams with complex workflows",
    features: ["Up to 25 agents", "10,000 runs/month", "Priority support", "Custom integrations"],
    popular: true,
  },
  {
    id: "scale",
    name: "Scale",
    price: "$999",
    description: "For enterprises with advanced needs",
    features: ["Unlimited agents", "Unlimited runs", "24/7 support", "SSO & SAML", "Dedicated CSM"],
    popular: false,
  },
]

const useCases = [
  { id: "sales", label: "Sales & CRM", icon: Users },
  { id: "marketing", label: "Marketing Ops", icon: Sparkles },
  { id: "data", label: "Data & Analytics", icon: Zap },
  { id: "finance", label: "Finance & Reporting", icon: Building2 },
  { id: "support", label: "Customer Support", icon: Shield },
]

export default function GetStartedPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [selectedPlan, setSelectedPlan] = useState("growth")
  const [selectedUseCases, setSelectedUseCases] = useState<string[]>([])
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)

  const handleOAuth = async (provider: string) => {
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setStep(2)
    setIsLoading(false)
  }

  const handleEmailSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setStep(2)
    setIsLoading(false)
  }

  const handleCompanySetup = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 800))
    setStep(3)
    setIsLoading(false)
  }

  const handlePlanSelect = () => {
    setStep(4)
  }

  const handleComplete = async () => {
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    router.push("/onboarding")
  }

  const toggleUseCase = (id: string) => {
    setSelectedUseCases(prev => 
      prev.includes(id) ? prev.filter(u => u !== id) : [...prev, id]
    )
  }

  return (
    <div className="min-h-screen flex bg-white">
      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Progress indicator */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {[1, 2, 3, 4].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <motion.div
                  className={`h-2 rounded-full transition-all ${
                    s === step ? "w-8 bg-emerald-500" : s < step ? "w-2 bg-emerald-500" : "w-2 bg-zinc-200"
                  }`}
                  layoutId={`step-${s}`}
                />
              </div>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {/* Step 1: Account Creation */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
              >
                {/* Enhanced header graphic */}
                <div className="text-center mb-8">
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
                    className="mb-6 relative inline-block"
                  >
                    {/* Main icon - Gravitre logo */}
                    <div className="h-20 w-20 mx-auto flex items-center justify-center">
                      <img 
                        src="/images/gravitre-icon.png" 
                        alt="Gravitre" 
                        className="h-20 w-20 object-contain"
                      />
                    </div>
                    {/* Floating mini icons */}
                    <motion.div
                      className="absolute -top-2 -right-2 h-8 w-8 rounded-lg bg-blue-500 shadow-lg flex items-center justify-center"
                      animate={{ y: [0, -4, 0], rotate: [0, 5, 0] }}
                      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    >
                      <Bot className="h-4 w-4 text-white" />
                    </motion.div>
                    <motion.div
                      className="absolute -bottom-1 -left-2 h-7 w-7 rounded-lg bg-amber-500 shadow-lg flex items-center justify-center"
                      animate={{ y: [0, 4, 0], rotate: [0, -5, 0] }}
                      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
                    >
                      <Workflow className="h-3.5 w-3.5 text-white" />
                    </motion.div>
                  </motion.div>
                  <h1 className="text-2xl font-semibold text-zinc-900">Create your account</h1>
                  <p className="mt-2 text-sm text-zinc-500">
                    Start your 7-day free trial. No credit card required.
                  </p>
                </div>

                {/* OAuth Buttons */}
                <div className="space-y-3 mb-6">
                  <button
                    onClick={() => handleOAuth("google")}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50 shadow-sm"
                  >
                    <svg className="h-5 w-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    Continue with Google
                  </button>
                  <button
                    onClick={() => handleOAuth("github")}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-50 hover:border-zinc-300 disabled:opacity-50 shadow-sm"
                  >
                    <Github className="h-5 w-5" />
                    Continue with GitHub
                  </button>
                </div>

                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-zinc-200" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-2 text-zinc-400">Or continue with email</span>
                  </div>
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
                      className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
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
                        className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 pr-10 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="Min. 8 characters"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
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
                      className="mt-1 h-4 w-4 rounded border-zinc-300 text-emerald-500 focus:ring-emerald-500"
                    />
                    <label htmlFor="terms" className="text-xs text-zinc-500">
                      I agree to the{" "}
                      <Link href="/terms" className="text-emerald-600 hover:text-emerald-500">Terms of Service</Link>
                      {" "}and{" "}
                      <Link href="/privacy" className="text-emerald-600 hover:text-emerald-500">Privacy Policy</Link>
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading || !agreedToTerms}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800 disabled:opacity-50 shadow-sm"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        Create account
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </form>

                <p className="mt-6 text-center text-sm text-zinc-500">
                  Already have an account?{" "}
                  <Link href="/login" className="text-emerald-600 hover:text-emerald-500 font-medium">
                    Sign in
                  </Link>
                </p>
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
              >
                <button
                  onClick={() => setStep(1)}
                  className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 mb-6"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>

                <h1 className="text-2xl font-semibold text-zinc-900">Set up your workspace</h1>
                <p className="mt-2 text-sm text-zinc-500 mb-8">
                  Tell us a bit about your organization
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
                      className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                      placeholder="Acme Inc"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-3">
                      What will you use Gravitre for?
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {useCases.map((useCase) => {
                        const Icon = useCase.icon
                        const isSelected = selectedUseCases.includes(useCase.id)
                        return (
                          <button
                            key={useCase.id}
                            type="button"
                            onClick={() => toggleUseCase(useCase.id)}
                            className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all ${
                              isSelected
                                ? "border-emerald-500 bg-emerald-50"
                                : "border-zinc-200 bg-white hover:border-zinc-300"
                            }`}
                          >
                            <Icon className={`h-4 w-4 ${isSelected ? "text-emerald-600" : "text-zinc-400"}`} />
                            <span className={`text-sm ${isSelected ? "text-zinc-900" : "text-zinc-600"}`}>
                              {useCase.label}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading || !companyName}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800 disabled:opacity-50 shadow-sm"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        Continue
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
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
                className="max-w-lg"
              >
                <button
                  onClick={() => setStep(2)}
                  className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 mb-6"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>

                <h1 className="text-2xl font-semibold text-zinc-900">Choose your plan</h1>
                <p className="mt-2 text-sm text-zinc-500 mb-8">
                  Start with a 7-day free trial. Cancel anytime.
                </p>

                <div className="space-y-3">
                  {plans.map((plan) => (
                    <button
                      key={plan.id}
                      onClick={() => setSelectedPlan(plan.id)}
                      className={`w-full rounded-xl border p-4 text-left transition-all ${
                        selectedPlan === plan.id
                          ? "border-emerald-500 bg-emerald-50"
                          : "border-zinc-200 bg-white hover:border-zinc-300"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                            selectedPlan === plan.id ? "border-emerald-500" : "border-zinc-300"
                          }`}>
                            {selectedPlan === plan.id && (
                              <div className="h-2 w-2 rounded-full bg-emerald-500" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-zinc-900">{plan.name}</span>
                              {plan.popular && (
                                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700 font-medium">
                                  Popular
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-zinc-500 mt-0.5">{plan.description}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-semibold text-zinc-900">{plan.price}</span>
                          <span className="text-xs text-zinc-500">/mo</span>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {plan.features.slice(0, 3).map((feature) => (
                          <span key={feature} className="flex items-center gap-1 text-xs text-zinc-500">
                            <Check className="h-3 w-3 text-emerald-500" />
                            {feature}
                          </span>
                        ))}
                      </div>
                    </button>
                  ))}
                </div>

                <button
                  onClick={handlePlanSelect}
                  className="w-full mt-6 flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800 shadow-sm"
                >
                  Start free trial
                  <ArrowRight className="h-4 w-4" />
                </button>

                <p className="mt-4 text-center text-xs text-zinc-500">
                  No credit card required for trial
                </p>
              </motion.div>
            )}

            {/* Step 4: Confirmation */}
            {step === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="text-center"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100"
                >
                  <Check className="h-8 w-8 text-emerald-600" />
                </motion.div>

                <h1 className="text-2xl font-semibold text-zinc-900">You&apos;re all set!</h1>
                <p className="mt-2 text-sm text-zinc-500 mb-8">
                  Your workspace for <span className="text-zinc-900 font-medium">{companyName || "your company"}</span> is ready.
                </p>

                <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 mb-6">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-zinc-500">Plan</span>
                    <span className="text-zinc-900 font-medium capitalize">{selectedPlan} (7-day trial)</span>
                  </div>
                </div>

                <button
                  onClick={handleComplete}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800 disabled:opacity-50 shadow-sm"
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      Enter Gravitre
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Right side - Visual */}
      <div className="hidden lg:flex flex-1 items-center justify-center bg-gradient-to-br from-zinc-50 via-emerald-50/30 to-zinc-50 p-12 relative overflow-hidden border-l border-zinc-200">
        {/* Animated background elements */}
        <div className="absolute inset-0">
          <motion.div
            animate={{ 
              x: [0, 100, 0],
              y: [0, -50, 0],
            }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
            className="absolute top-1/4 left-1/4 h-64 w-64 rounded-full bg-emerald-200/30 blur-3xl"
          />
          <motion.div
            animate={{ 
              x: [0, -80, 0],
              y: [0, 80, 0],
            }}
            transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
            className="absolute bottom-1/4 right-1/4 h-48 w-48 rounded-full bg-blue-200/30 blur-3xl"
          />
        </div>

        <div className="relative z-10 max-w-md">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">
              Join 500+ companies automating with AI
            </h2>
            <p className="text-zinc-600 mb-8">
              From startups to enterprises, teams use Gravitre to orchestrate their AI workforce and automate complex operations.
            </p>

            {/* Logos */}
            <div className="grid grid-cols-3 gap-6 opacity-40">
              {["Vercel", "Linear", "Notion", "Figma", "Stripe", "Slack"].map((company) => (
                <div key={company} className="flex items-center justify-center">
                  <span className="text-sm text-zinc-600 font-medium">{company}</span>
                </div>
              ))}
            </div>

            {/* Stats */}
            <div className="mt-12 grid grid-cols-3 gap-6">
              <div>
                <div className="text-2xl font-semibold text-zinc-900">98%</div>
                <div className="text-xs text-zinc-500">Task success rate</div>
              </div>
              <div>
                <div className="text-2xl font-semibold text-zinc-900">10M+</div>
                <div className="text-xs text-zinc-500">Tasks automated</div>
              </div>
              <div>
                <div className="text-2xl font-semibold text-zinc-900">4.9/5</div>
                <div className="text-xs text-zinc-500">Customer rating</div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
