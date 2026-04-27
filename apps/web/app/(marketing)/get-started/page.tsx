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
  Bot,
  Workflow,
  ChevronRight,
  Rocket
} from "lucide-react"

const plans = [
  {
    id: "starter",
    name: "Starter",
    price: "$79",
    description: "Perfect for small teams",
    features: ["5 agents", "1K runs/mo", "Email support"],
    popular: false,
  },
  {
    id: "growth",
    name: "Growth",
    price: "$299",
    description: "For growing teams",
    features: ["25 agents", "10K runs/mo", "Priority support"],
    popular: true,
  },
  {
    id: "scale",
    name: "Scale",
    price: "$999",
    description: "Enterprise scale",
    features: ["Unlimited", "SSO", "Dedicated CSM"],
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

// Animated grid background
function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Base gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-black" />
      
      {/* Animated grid */}
      <div 
        className="absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />
      
      {/* Glowing orbs */}
      <motion.div
        animate={{ 
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-1/4 left-1/4 h-[500px] w-[500px] rounded-full bg-emerald-500/10 blur-[120px]"
      />
      <motion.div
        animate={{ 
          scale: [1.2, 1, 1.2],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-1/4 right-1/4 h-[400px] w-[400px] rounded-full bg-blue-500/10 blur-[100px]"
      />
      
      {/* Floating particles */}
      {[...Array(20)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute h-1 w-1 rounded-full bg-white/20"
          style={{
            top: `${Math.random() * 100}%`,
            left: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [0, -30, 0],
            opacity: [0.2, 0.5, 0.2],
          }}
          transition={{
            duration: 3 + Math.random() * 2,
            repeat: Infinity,
            delay: Math.random() * 2,
          }}
        />
      ))}
    </div>
  )
}

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
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)

  const handleOAuth = async (provider: string) => {
    setLoadingProvider(provider)
    await new Promise(resolve => setTimeout(resolve, 1200))
    setStep(2)
    setLoadingProvider(null)
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

  const stepTitles = [
    { title: "Create account", subtitle: "7-day free trial" },
    { title: "Your workspace", subtitle: "Tell us about you" },
    { title: "Select plan", subtitle: "Pick what fits" },
    { title: "Ready to go", subtitle: "Launch time" },
  ]

  return (
    <div className="min-h-screen relative overflow-hidden bg-black">
      <GridBackground />
      
      {/* Top navigation */}
      <div className="relative z-20 flex items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <img 
            src="/images/gravitre-logo-white.png" 
            alt="Gravitre" 
            className="h-6"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
              e.currentTarget.nextElementSibling?.classList.remove('hidden')
            }}
          />
          <span className="text-white font-semibold text-lg hidden">Gravitre</span>
        </Link>
        <Link 
          href="/login" 
          className="text-sm text-zinc-400 hover:text-white transition-colors"
        >
          Already have an account?
        </Link>
      </div>
      
      {/* Main content */}
      <div className="relative z-10 flex items-center justify-center min-h-[calc(100vh-72px)] px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-lg"
        >
          {/* Step indicator - pill style */}
          <div className="flex items-center justify-center gap-1 mb-6">
            {stepTitles.map((s, i) => (
              <button
                key={i}
                onClick={() => i + 1 < step && setStep(i + 1)}
                disabled={i + 1 >= step}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  i + 1 === step 
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" 
                    : i + 1 < step 
                      ? "bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800 cursor-pointer" 
                      : "bg-zinc-900/50 text-zinc-600"
                }`}
              >
                {i + 1 < step ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <span className="h-4 w-4 rounded-full bg-current/20 flex items-center justify-center text-[10px]">
                    {i + 1}
                  </span>
                )}
                <span className="hidden sm:inline">{s.title}</span>
              </button>
            ))}
          </div>

          {/* Card */}
          <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl border border-zinc-800/80 shadow-2xl shadow-black/50 overflow-hidden">
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
                    <h1 className="text-2xl font-bold text-white">Start your journey</h1>
                    <p className="mt-2 text-sm text-zinc-400">
                      7-day free trial. No credit card needed.
                    </p>
                  </div>

                  {/* OAuth Buttons */}
                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <button
                      onClick={() => handleOAuth("google")}
                      disabled={loadingProvider !== null}
                      className="flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-zinc-900 transition-all hover:bg-zinc-100 disabled:opacity-50"
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
                          Google
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleOAuth("github")}
                      disabled={loadingProvider !== null}
                      className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-700 disabled:opacity-50"
                    >
                      {loadingProvider === "github" ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <>
                          <Github className="h-5 w-5" />
                          GitHub
                        </>
                      )}
                    </button>
                  </div>

                  <div className="relative my-6">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-zinc-800" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-zinc-900 px-3 text-zinc-500">or with email</span>
                    </div>
                  </div>

                  <form onSubmit={handleEmailSignup} className="space-y-4">
                    <div>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        className="w-full rounded-xl bg-zinc-800/50 border border-zinc-700/50 px-4 py-3 text-sm text-white placeholder-zinc-500 transition-all focus:border-emerald-500/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="Work email"
                      />
                    </div>

                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        minLength={8}
                        className="w-full rounded-xl bg-zinc-800/50 border border-zinc-700/50 px-4 py-3 pr-10 text-sm text-white placeholder-zinc-500 transition-all focus:border-emerald-500/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="Password (min 8 chars)"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>

                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        id="terms"
                        checked={agreedToTerms}
                        onChange={(e) => setAgreedToTerms(e.target.checked)}
                        className="mt-1 h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-emerald-500 focus:ring-emerald-500/20"
                      />
                      <label htmlFor="terms" className="text-xs text-zinc-400">
                        I agree to the{" "}
                        <Link href="/terms" className="text-emerald-400 hover:text-emerald-300">Terms</Link>
                        {" "}and{" "}
                        <Link href="/privacy" className="text-emerald-400 hover:text-emerald-300">Privacy Policy</Link>
                      </label>
                    </div>

                    <button
                      type="submit"
                      disabled={isLoading || !agreedToTerms}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 shadow-lg shadow-emerald-500/20"
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
                    className="flex items-center gap-1 text-sm text-zinc-500 hover:text-white mb-6 transition-colors"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </button>

                  <h1 className="text-2xl font-bold text-white">Set up workspace</h1>
                  <p className="mt-2 text-sm text-zinc-400 mb-8">
                    Quick setup for your team
                  </p>

                  <form onSubmit={handleCompanySetup} className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-zinc-300 mb-2">
                        Company name
                      </label>
                      <input
                        type="text"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        required
                        className="w-full rounded-xl bg-zinc-800/50 border border-zinc-700/50 px-4 py-3 text-sm text-white placeholder-zinc-500 transition-all focus:border-emerald-500/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                        placeholder="Acme Inc"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zinc-300 mb-3">
                        Primary use case
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
                                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                  : "bg-zinc-800/50 text-zinc-400 border border-zinc-700/50 hover:border-zinc-600"
                              }`}
                            >
                              <Icon className="h-4 w-4" />
                              {useCase.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={isLoading || !companyName}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 shadow-lg shadow-emerald-500/20"
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
                  className="p-8"
                >
                  <button
                    onClick={() => setStep(2)}
                    className="flex items-center gap-1 text-sm text-zinc-500 hover:text-white mb-6 transition-colors"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </button>

                  <h1 className="text-2xl font-bold text-white">Choose your plan</h1>
                  <p className="mt-2 text-sm text-zinc-400 mb-6">
                    7-day free trial on all plans
                  </p>

                  <div className="space-y-3">
                    {plans.map((plan) => (
                      <button
                        key={plan.id}
                        onClick={() => setSelectedPlan(plan.id)}
                        className={`w-full rounded-xl border p-4 text-left transition-all ${
                          selectedPlan === plan.id
                            ? "border-emerald-500/50 bg-emerald-500/10"
                            : "border-zinc-700/50 bg-zinc-800/30 hover:border-zinc-600"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                              selectedPlan === plan.id ? "border-emerald-500" : "border-zinc-600"
                            }`}>
                              {selectedPlan === plan.id && (
                                <div className="h-2 w-2 rounded-full bg-emerald-500" />
                              )}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white">{plan.name}</span>
                                {plan.popular && (
                                  <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400 font-medium">
                                    Popular
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-zinc-500">{plan.description}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-lg font-bold text-white">{plan.price}</span>
                            <span className="text-xs text-zinc-500">/mo</span>
                          </div>
                        </div>
                        <div className="mt-3 flex gap-3">
                          {plan.features.map((feature) => (
                            <span key={feature} className="flex items-center gap-1 text-xs text-zinc-400">
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
                    className="w-full mt-6 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600 shadow-lg shadow-emerald-500/20"
                  >
                    Start free trial
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </motion.div>
              )}

              {/* Step 4: Confirmation */}
              {step === 4 && (
                <motion.div
                  key="step4"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.5 }}
                  className="p-8 text-center"
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                    className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30"
                  >
                    <Check className="h-8 w-8 text-white" />
                  </motion.div>

                  <h1 className="text-2xl font-bold text-white">You&apos;re all set!</h1>
                  <p className="mt-2 text-sm text-zinc-400 mb-8">
                    Welcome to <span className="text-white font-medium">{companyName || "Gravitre"}</span>
                  </p>

                  <div className="rounded-xl border border-zinc-700/50 bg-zinc-800/30 p-4 mb-6 text-left">
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-zinc-400">Plan</span>
                      <span className="text-white font-medium capitalize">{selectedPlan}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-400">Trial</span>
                      <span className="text-emerald-400 font-medium">7 days free</span>
                    </div>
                  </div>

                  <button
                    onClick={handleComplete}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3 text-sm font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 shadow-lg shadow-emerald-500/20"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        Launch Gravitre
                        <Rocket className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Trust badges below card */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="flex items-center justify-center gap-6 mt-8 text-zinc-500"
          >
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              <span className="text-xs">SOC 2</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4" />
              <span className="text-xs">99.9% uptime</span>
            </div>
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              <span className="text-xs">500+ teams</span>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}
