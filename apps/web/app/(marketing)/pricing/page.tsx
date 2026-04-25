"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Check, ArrowRight, HelpCircle, Zap, Play, Mail, FileText, Send, ChevronRight, Users, Crown, Smartphone, Monitor, Building2, Rocket, Info, Shield, Cpu, Sparkles, X, Blocks, Star, Clock, BadgeCheck, RefreshCcw, Minus } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// Role definitions for tooltips
const roles = {
  masterAdmin: {
    name: "Master Admin",
    description: "Full system control, billing, and organization management. Automatically included.",
    icon: Crown,
  },
  coreUser: {
    name: "Core User",
    description: "Builds and configures agents. Full access to Gravitre Core for creating workflows and managing outputs.",
    icon: Monitor,
  },
  liteUser: {
    name: "Lite User",
    description: "Assigns work and views outputs using Gravitre Lite. Mobile-first interface for team-wide adoption.",
    icon: Smartphone,
  },
}

const tiers = [
  {
    name: "Node",
    tagline: "Focused execution for small teams",
    price: { monthly: 49, annual: 41 },
    description: "Generate complete outputs like campaigns, reports, or workflows—without building everything from scratch.",
    outputs: "Up to 10 complete outputs / month",
    team: {
      agents: "1 Agent",
      coreUsers: "1 Core User",
      liteUsers: "2 Lite Users",
    },
    meson: null, // No Meson access
    features: [
      "Email delivery",
      "Basic campaign outputs",
      "3 app integrations",
      "Community support",
    ],
    cta: "Start 7-day free trial",
    highlighted: false,
    color: "emerald",
    gradient: "from-emerald-500 to-emerald-600",
    glow: "emerald-500/20",
    icon: Zap,
  },
  {
    name: "Control",
    tagline: "Coordinate work across your systems",
    price: { monthly: 129, annual: 107 },
    description: "Plan and execute multi-step work across email, CRM, and data sources with full campaign capabilities.",
    outputs: "Up to 40 complete outputs / month",
    team: {
      agents: "2-3 Agents",
      coreUsers: "2 Core Users",
      liteUsers: "5 Lite Users",
    },
    meson: { count: 10, label: "10 Mesons / month" },
    features: [
      "CRM + Outlook integrations",
      "Multi-step execution",
      "Full campaign outputs",
      "Slack delivery",
      "Priority support",
    ],
    cta: "Start 7-day free trial",
    highlighted: true,
    badge: "Most Popular",
    color: "amber",
    gradient: "from-amber-500 to-orange-500",
    glow: "amber-500/30",
    icon: Building2,
  },
  {
    name: "Command",
    tagline: "Run AI agents across your entire team",
    price: { monthly: 299, annual: 249 },
    description: "Deploy multiple agents that collaborate, execute, and deliver work across your organization.",
    outputs: "Up to 120 complete outputs / month",
    team: {
      agents: "5-8 Agents",
      coreUsers: "5 Core Users",
      liteUsers: "Unlimited Lite Users",
    },
    meson: { count: 40, label: "40 Mesons / month" },
    features: [
      "Approvals + workflows",
      "Advanced integrations",
      "Team collaboration workspace",
      "Cross-department agents",
      "Dedicated support",
      "Custom agent training",
    ],
    cta: "Start 7-day free trial",
    highlighted: false,
    color: "blue",
    gradient: "from-blue-500 to-indigo-500",
    glow: "blue-500/20",
    icon: Rocket,
  },
]

const addOns = [
  {
    name: "Additional Core Users",
    price: "$29/month each",
    description: "Add more builders and configurers to your team",
    icon: Users,
  },
  {
    name: "Additional Outputs",
    price: "$2-$3 each",
    description: "Pay-as-you-go for extra capacity when needed",
    icon: Zap,
  },
  {
    name: "Additional Mesons",
    price: "$2-$4 each",
    description: "Build more systems on demand (Control + Command only)",
    icon: Blocks,
  },
]

const faqs = [
  {
    question: "What counts as an output?",
    answer: "An output is a complete piece of work: a full email sequence, a campaign brief, a segment list, a report, or an automation workflow. Simple edits or previews don't count—only delivered or exported work.",
  },
  {
    question: "What's the difference between Core and Lite users?",
    answer: "Core Users build and configure agents using Gravitre Core—the full desktop experience. Lite Users assign work and view outputs through Gravitre Lite, a mobile-first interface designed for team-wide adoption without requiring everyone to learn the full system.",
  },
  {
    question: "Can I edit before sending?",
    answer: "Absolutely. Every output goes through a review step where you can edit, adjust, or approve before it's delivered. You have full control over what gets sent.",
  },
  {
    question: "How does the free trial work?",
    answer: "You get 7 days of full access to your chosen plan. No credit card required to start. If you don't subscribe, your workspace pauses—nothing gets deleted.",
  },
  {
    question: "What happens after I hit my limit?",
    answer: "We'll notify you as you approach your limit. You can purchase additional outputs at $2–$3 each, or upgrade your plan for more capacity.",
  },
  {
    question: "Can I cancel anytime?",
    answer: "Yes. Cancel anytime from your settings. Your access continues until the end of your billing period. No penalties, no hassle.",
  },
  {
    question: "Do agents learn my business?",
    answer: "Yes. Agents are trained on your brand voice, ICP, messaging framework, and historical work. The more you use them, the more aligned they become with how your team operates.",
  },
  {
    question: "Can agents be shared across departments?",
    answer: "Yes. Agents can be configured per department or shared across teams. Command plan includes cross-department agent capabilities for organization-wide workflows.",
  },
  {
    question: "What is Meson?",
    answer: "Meson is our system builder. It creates agents, training configurations, and workflows from a single request. Instead of manually setting everything up, describe what you need and Meson builds it. Available in Control and Command plans.",
  },
  {
    question: "How do Mesons work?",
    answer: "A Meson is one system-building request. You describe what you want to create (an agent, workflow, or training setup), and Meson generates everything you need. Usage is only triggered when you click 'Run Meson'—not while typing or exploring.",
  },
]

const howItWorks = [
  {
    step: "01",
    title: "Create or select your agent",
    description: "Choose a pre-built agent or train one on your business context, brand voice, and tools.",
    icon: Zap,
  },
  {
    step: "02",
    title: "Describe the work",
    description: "Tell the agent what you need in plain language. Add context, files, or reference materials.",
    icon: FileText,
  },
  {
    step: "03",
    title: "Agent plans and executes",
    description: "The agent breaks down the work, gathers data, and builds complete outputs.",
    icon: Play,
  },
  {
    step: "04",
    title: "Receive complete outputs",
    description: "Review, edit, and deliver results to Outlook, Slack, CRM, or export directly.",
    icon: Send,
  },
]

function RoleTooltip({ role, children }: { role: keyof typeof roles; children: React.ReactNode }) {
  const roleData = roles[role]
  const Icon = roleData.icon
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 cursor-help border-b border-dashed border-zinc-300">
            {children}
            <Info className="h-3 w-3 text-zinc-400" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs bg-white border-zinc-200 text-zinc-900 p-3 shadow-lg">
          <div className="flex items-start gap-2">
            <div className="h-6 w-6 rounded-md bg-zinc-100 flex items-center justify-center shrink-0 mt-0.5">
              <Icon className="h-3.5 w-3.5 text-zinc-600" />
            </div>
            <div>
              <p className="font-medium text-sm text-zinc-900">{roleData.name}</p>
              <p className="text-xs text-zinc-500 mt-1">{roleData.description}</p>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function PricingCard({ tier, isAnnual, index }: { tier: typeof tiers[0]; isAnnual: boolean; index: number }) {
  const price = isAnnual ? tier.price.annual : tier.price.monthly
  const TierIcon = tier.icon
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="group relative"
    >
      {/* Glow effect for highlighted */}
      {tier.highlighted && (
        <div className={`absolute -inset-px rounded-3xl bg-gradient-to-b ${tier.gradient} blur-xl opacity-20 group-hover:opacity-30 transition-opacity`} />
      )}
      
      <div className={`relative h-full rounded-2xl sm:rounded-3xl border p-5 sm:p-8 transition-all ${
        tier.highlighted
          ? "border-amber-300 bg-amber-50/50 shadow-lg"
          : "border-zinc-200 bg-white hover:border-zinc-300 hover:shadow-md"
      }`}>
        {/* Badge */}
        {tier.badge && (
          <div className="absolute -top-4 left-1/2 -translate-x-1/2">
            <motion.span 
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3 }}
              className={`inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r ${tier.gradient} px-4 py-1.5 text-xs font-semibold text-white shadow-lg`}
            >
              {tier.badge}
            </motion.span>
          </div>
        )}
        
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className={`h-8 w-8 rounded-lg bg-gradient-to-r ${tier.gradient} flex items-center justify-center`}>
              <TierIcon className="h-4 w-4 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-zinc-900">{tier.name}</h3>
          </div>
          <p className="text-sm text-zinc-500">{tier.tagline}</p>
        </div>

        {/* Price */}
        <div className="mb-5 sm:mb-6">
          <div className="flex items-baseline gap-1">
            <span className="text-4xl sm:text-5xl font-bold text-zinc-900">
              ${price}
            </span>
            <span className="text-zinc-500 text-sm sm:text-base">/month</span>
          </div>
          {isAnnual && (
            <motion.p 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-1 text-xs text-emerald-600"
            >
              Billed annually (save ${(tier.price.monthly - tier.price.annual) * 12}/year)
            </motion.p>
          )}
        </div>

        {/* Team Structure */}
        <div className="mb-6 p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Team Structure</p>
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-600 flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-zinc-400" />
                Agents
              </span>
              <span className="text-sm font-medium text-zinc-900">{tier.team.agents}</span>
            </div>
            <div className="flex items-center justify-between">
              <RoleTooltip role="coreUser">
                <span className="text-sm text-zinc-600 flex items-center gap-2">
                  <Monitor className="h-3.5 w-3.5 text-zinc-400" />
                  Core Users
                </span>
              </RoleTooltip>
              <span className="text-sm font-medium text-zinc-900">{tier.team.coreUsers}</span>
            </div>
            <div className="flex items-center justify-between">
              <RoleTooltip role="liteUser">
                <span className="text-sm text-zinc-600 flex items-center gap-2">
                  <Smartphone className="h-3.5 w-3.5 text-zinc-400" />
                  Lite Users
                </span>
              </RoleTooltip>
              <span className="text-sm font-medium text-zinc-900">{tier.team.liteUsers}</span>
            </div>
          </div>
        </div>

        {/* Output limit - highlighted */}
        <div className={`mb-4 p-4 rounded-2xl`}
          style={{ background: `linear-gradient(to right, rgb(${tier.color === 'emerald' ? '16 185 129' : tier.color === 'amber' ? '245 158 11' : '59 130 246'} / 0.1), transparent)` }}
        >
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full bg-gradient-to-r ${tier.gradient}`} />
            <span className="text-sm font-semibold text-zinc-900">{tier.outputs}</span>
          </div>
          <p className="mt-1 text-xs text-zinc-500">Campaigns, email sequences, reports, workflows</p>
        </div>

        {/* Meson section */}
        <div className={`mb-6 p-4 rounded-2xl border ${tier.meson ? 'border-violet-200 bg-violet-50' : 'border-zinc-200 bg-zinc-50'}`}>
          <div className="flex items-center gap-2 mb-2">
            <Blocks className={`h-4 w-4 ${tier.meson ? 'text-violet-600' : 'text-zinc-400'}`} />
            <span className={`text-xs font-semibold uppercase tracking-wider ${tier.meson ? 'text-violet-600' : 'text-zinc-400'}`}>
              Meson
            </span>
          </div>
          {tier.meson ? (
            <>
              <p className="text-sm font-medium text-zinc-900">{tier.meson.label}</p>
              <p className="mt-1 text-xs text-zinc-500">Build systems from a single request</p>
            </>
          ) : (
            <>
              <p className="text-sm text-zinc-400 flex items-center gap-2">
                <X className="h-3.5 w-3.5" />
                Not included
              </p>
              <p className="mt-1 text-xs text-zinc-400">Upgrade to Control for Meson access</p>
            </>
          )}
        </div>
        
        {/* Features */}
        <ul className="mb-8 space-y-3">
          {tier.features.map((feature, i) => (
            <motion.li 
              key={feature}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
              className="flex items-start gap-3"
            >
              <div className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                tier.highlighted ? "bg-amber-100" : "bg-zinc-100"
              }`}>
                <Check className={`h-3 w-3 ${tier.highlighted ? "text-amber-600" : "text-zinc-500"}`} />
              </div>
              <span className="text-sm text-zinc-600">{feature}</span>
            </motion.li>
          ))}
        </ul>
        
        {/* CTA */}
        <Link
          href="/get-started"
          className={`group/btn inline-flex w-full items-center justify-center gap-2 rounded-full px-6 py-3.5 text-sm font-semibold transition-all ${
            tier.highlighted
              ? "bg-zinc-900 text-white hover:bg-zinc-800 shadow-lg shadow-zinc-900/20"
              : "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50 hover:border-zinc-400"
          }`}
        >
          {tier.cta}
          <ArrowRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
        </Link>

        <p className="mt-3 text-center text-xs text-zinc-500">No credit card required</p>
      </div>
    </motion.div>
  )
}

export default function PricingPage() {
  const [isAnnual, setIsAnnual] = useState(true)
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)

  return (
    <div className="relative overflow-hidden bg-white">
      {/* Hero */}
      <section className="relative py-24 sm:py-32 overflow-hidden">
        {/* Static background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-amber-50 via-transparent to-transparent" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-amber-100/30 rounded-full blur-3xl" />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-3xl text-center"
          >
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50/80 backdrop-blur-sm px-4 py-2"
            >
              <motion.div 
                className="h-2 w-2 rounded-full bg-amber-500"
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <span className="text-sm font-medium text-amber-700">Simple, transparent pricing</span>
            </motion.div>
            
            {/* Headline with staggered animation */}
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight"
              >
                <span className="text-zinc-900">
                  Deploy AI that actually
                </span>
              </motion.h1>
            </div>
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight"
              >
                <span className="bg-gradient-to-r from-amber-600 to-orange-500 bg-clip-text text-transparent">
                  does the work.
                </span>
              </motion.h1>
            </div>
            
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mt-6 text-lg text-zinc-600 leading-relaxed"
            >
              Assign work. Get results. Gravitre agents plan, build, and deliver complete outputs across your tools.
            </motion.p>

            <motion.p 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-3 text-sm text-zinc-500"
            >
              Replace hours of work with a single task.
            </motion.p>
            
            {/* Billing toggle with enhanced animation */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="mt-8 sm:mt-10 inline-flex items-center gap-2 sm:gap-4 rounded-full border border-zinc-200 bg-white/80 backdrop-blur-sm p-1 sm:p-1.5 shadow-lg shadow-zinc-200/50"
            >
              <button
                onClick={() => setIsAnnual(false)}
                className={`relative rounded-full px-4 sm:px-6 py-2 text-xs sm:text-sm font-medium transition-all ${
                  !isAnnual 
                    ? "bg-zinc-900 text-white shadow-sm" 
                    : "text-zinc-500 hover:text-zinc-900"
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setIsAnnual(true)}
                className={`relative rounded-full px-4 sm:px-6 py-2 text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 sm:gap-2 ${
                  isAnnual 
                    ? "bg-zinc-900 text-white shadow-sm" 
                    : "text-zinc-500 hover:text-zinc-900"
                }`}
              >
                Annual
                <motion.span 
                  className={`text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded-full ${
                    isAnnual ? "bg-emerald-500 text-white" : "bg-emerald-100 text-emerald-600"
                  }`}
                  animate={isAnnual ? { scale: [1, 1.05, 1] } : {}}
                  transition={{ duration: 0.5 }}
                >
                  2 months free
                </motion.span>
              </button>
            </motion.div>
            <motion.p 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
              className="mt-3 text-xs text-zinc-500"
            >
              Save with annual billing
            </motion.p>
          </motion.div>
        </div>
      </section>

      {/* Role Explanation Section */}
      <section className="relative pb-16">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-zinc-200 bg-white p-6 sm:p-8 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-6">
              <Users className="h-5 w-5 text-zinc-500" />
              <h3 className="text-lg font-semibold text-zinc-900">How teams use Gravitre</h3>
            </div>
            
            <div className="grid sm:grid-cols-3 gap-6">
              {/* Core Users */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-blue-100 flex items-center justify-center">
                    <Monitor className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900">Core Users</p>
                    <p className="text-xs text-zinc-500">Gravitre Core</p>
                  </div>
                </div>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Build and configure agents, create workflows, and manage outputs. Full access to the desktop experience.
                </p>
              </div>

              {/* Lite Users */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                    <Smartphone className="h-5 w-5 text-emerald-600" />
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900">Lite Users</p>
                    <p className="text-xs text-zinc-500">Gravitre Lite</p>
                  </div>
                </div>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Assign work and view outputs on mobile. Perfect for team-wide adoption without the learning curve.
                </p>
              </div>

              {/* Master Admin */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-amber-100 flex items-center justify-center">
                    <Crown className="h-5 w-5 text-amber-600" />
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900">Master Admin</p>
                    <p className="text-xs text-zinc-500">Included</p>
                  </div>
                </div>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Full system control, billing management, and organization settings. One per account.
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="relative pb-16 sm:pb-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="grid gap-4 sm:gap-8 lg:grid-cols-3">
            {tiers.map((tier, i) => (
              <PricingCard key={tier.name} tier={tier} isAnnual={isAnnual} index={i} />
            ))}
          </div>
          
          {/* Add-ons Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="mt-12 rounded-2xl border border-zinc-200 bg-white p-6 sm:p-8 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-6">
              <HelpCircle className="h-5 w-5 text-zinc-500" />
              <h3 className="text-lg font-semibold text-zinc-900">Need more?</h3>
            </div>
            
            <div className="grid sm:grid-cols-3 gap-6">
              {addOns.map((addon, i) => {
                const AddonIcon = addon.icon
                return (
                  <div key={i} className="flex items-start gap-4">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${
                      addon.name.includes('Meson') ? 'bg-violet-100' : 'bg-zinc-100'
                    }`}>
                      <AddonIcon className={`h-5 w-5 ${addon.name.includes('Meson') ? 'text-violet-600' : 'text-zinc-500'}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-3 flex-wrap">
                        <p className="font-medium text-zinc-900">{addon.name}</p>
                        <span className={`text-sm font-medium ${addon.name.includes('Meson') ? 'text-violet-600' : 'text-emerald-600'}`}>
                          {addon.price}
                        </span>
                      </div>
                      <p className="text-sm text-zinc-500 mt-1">{addon.description}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </motion.div>
          
          {/* Enterprise CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-8 rounded-3xl border border-zinc-200 bg-gradient-to-br from-zinc-50 to-white p-8 text-center shadow-sm"
          >
            <h3 className="text-xl font-semibold text-zinc-900">Need enterprise scale?</h3>
            <p className="mt-2 text-zinc-600">
              Custom agent counts, SLAs, dedicated infrastructure, and white-glove onboarding.
            </p>
            <Link
              href="/contact"
              className="mt-6 inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-3 text-sm font-semibold text-zinc-900 transition-all hover:bg-zinc-50 hover:border-zinc-400 shadow-sm"
            >
              Talk to Sales
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Meson Section */}
      <section className="relative py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-b from-violet-50 via-transparent to-transparent" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-violet-100 rounded-full blur-3xl opacity-30" />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-4xl"
          >
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 mb-4 rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5">
                <Blocks className="h-4 w-4 text-violet-600" />
                <span className="text-sm font-medium text-violet-700">System Builder</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
                Build your system with Meson
              </h2>
              <p className="mt-4 text-lg text-zinc-600">
                Meson creates agents, training, and workflows from a single request.
              </p>
            </div>

            {/* Meson Visual Flow */}
            <div className="rounded-3xl border border-violet-200 bg-white p-8 shadow-sm">
              <div className="grid md:grid-cols-3 gap-6">
                {/* Input */}
                <div className="text-center">
                  <div className="mx-auto h-16 w-16 rounded-2xl bg-violet-100 border border-violet-200 flex items-center justify-center mb-4">
                    <FileText className="h-7 w-7 text-violet-600" />
                  </div>
                  <h3 className="font-semibold text-zinc-900 mb-2">Describe what you need</h3>
                  <p className="text-sm text-zinc-500">
                    {'"Create a marketing agent for SaaS onboarding campaigns"'}
                  </p>
                </div>

                {/* Arrow */}
                <div className="hidden md:flex items-center justify-center">
                  <div className="flex items-center gap-2">
                    <div className="h-px w-12 bg-gradient-to-r from-violet-300 to-violet-500" />
                    <Sparkles className="h-5 w-5 text-violet-500 animate-pulse" />
                    <div className="h-px w-12 bg-gradient-to-r from-violet-500 to-violet-300" />
                  </div>
                </div>

                {/* Output */}
                <div className="text-center">
                  <div className="mx-auto h-16 w-16 rounded-2xl bg-emerald-100 border border-emerald-200 flex items-center justify-center mb-4">
                    <Check className="h-7 w-7 text-emerald-600" />
                  </div>
                  <h3 className="font-semibold text-zinc-900 mb-2">Meson generates</h3>
                  <p className="text-sm text-zinc-500">
                    Agent config, training structure, workflows, sample outputs
                  </p>
                </div>
              </div>

              {/* CTA */}
              <div className="mt-8 pt-6 border-t border-zinc-100 text-center">
                <p className="text-sm text-zinc-600 mb-4">
                  Meson builds the system. Gravitre executes it.
                </p>
                <div className="inline-flex items-center gap-4 text-xs text-zinc-500">
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    Available in Control
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    Available in Command
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Value Explanation */}
      <section className="relative py-24 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-3xl"
          >
            <div className="text-center mb-12">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
                Not another AI tool. This is execution.
              </h2>
            </div>

            <div className="grid sm:grid-cols-2 gap-6">
              {[
                {
                  title: "Complete work, not suggestions",
                  description: "Gravitre doesn't generate ideas—it completes work. Full campaigns, sequences, and reports, delivered.",
                },
                {
                  title: "Hours replaced, not added",
                  description: "Each output replaces hours of manual effort. Work that took a day now takes minutes.",
                },
                {
                  title: "Direct delivery",
                  description: "Outputs delivered directly to your tools—email, CRM, Slack. No copy-paste required.",
                },
                {
                  title: "Learns your business",
                  description: "Agents are trained on your brand voice, ICP, and messaging. They get better with every use.",
                },
              ].map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6 hover:border-zinc-300 transition-colors"
                >
                  <h3 className="font-semibold text-zinc-900 mb-2">{item.title}</h3>
                  <p className="text-sm text-zinc-600 leading-relaxed">{item.description}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section className="relative py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              How it works
            </h2>
            <p className="mt-4 text-zinc-600">From request to delivery in four steps</p>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {howItWorks.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="relative"
              >
                {i < howItWorks.length - 1 && (
                  <div className="hidden lg:block absolute top-8 left-full w-full h-px bg-gradient-to-r from-zinc-300 to-transparent -translate-x-6" />
                )}
                <div className="rounded-2xl border border-zinc-200 bg-white p-6 h-full shadow-sm">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-100">
                      <item.icon className="h-5 w-5 text-zinc-600" />
                    </div>
                    <span className="text-xs font-mono text-zinc-400">{item.step}</span>
                  </div>
                  <h3 className="font-semibold text-zinc-900 mb-2">{item.title}</h3>
                  <p className="text-sm text-zinc-600 leading-relaxed">{item.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="relative py-24 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              Trusted by growing teams
            </h2>
            <p className="mt-4 text-zinc-600">See what teams are saying about Gravitre</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                quote: "Gravitre cut our campaign production time by 80%. What used to take our team 2 days now takes 20 minutes.",
                author: "Sarah Chen",
                role: "Marketing Director",
                company: "TechStart",
                rating: 5,
              },
              {
                quote: "The agents actually understand our brand voice. The outputs feel like they were written by someone who has been here for years.",
                author: "Marcus Johnson",
                role: "Head of Operations",
                company: "DataFlow",
                rating: 5,
              },
              {
                quote: "Meson is a game-changer. I described what I needed and had a fully configured agent in minutes, not hours.",
                author: "Emily Rodriguez",
                role: "Growth Lead",
                company: "CloudScale",
                rating: 5,
              },
            ].map((testimonial, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="relative rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex gap-1 mb-4">
                  {Array.from({ length: testimonial.rating }).map((_, j) => (
                    <Star key={j} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-zinc-700 leading-relaxed mb-6">{`"${testimonial.quote}"`}</p>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-zinc-200 to-zinc-300 flex items-center justify-center">
                    <span className="text-sm font-semibold text-zinc-600">
                      {testimonial.author.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900 text-sm">{testimonial.author}</p>
                    <p className="text-xs text-zinc-500">{testimonial.role}, {testimonial.company}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Company logos */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-16 pt-12 border-t border-zinc-200 text-center"
          >
            <p className="text-sm text-zinc-500 mb-8">Used by marketing and ops teams at</p>
            <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
              {["Acme Corp", "TechStart", "DataFlow", "CloudScale", "MarketEdge"].map((company) => (
                <span key={company} className="text-lg font-semibold text-zinc-300 hover:text-zinc-400 transition-colors">{company}</span>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="relative py-24 border-t border-zinc-200 bg-zinc-50 overflow-hidden">
        {/* Subtle background decoration */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-amber-100/30 to-transparent rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative mx-auto max-w-6xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <motion.span
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 py-1.5 text-sm font-medium text-zinc-600 mb-4"
            >
              <Sparkles className="h-4 w-4 text-amber-500" />
              Detailed comparison
            </motion.span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              Compare all features
            </h2>
            <p className="mt-4 text-zinc-600 max-w-xl mx-auto">
              See exactly what you get with each plan. All plans include our core platform features.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-3xl border border-zinc-200 bg-white overflow-hidden shadow-xl shadow-zinc-200/50"
          >
            {/* Plan Headers with Pricing */}
            <div className="grid grid-cols-4 border-b border-zinc-200">
              <div className="p-6 bg-zinc-50">
                <span className="text-sm font-medium text-zinc-500">Features by plan</span>
              </div>
              {[
                { name: "Node", price: "$41", desc: "For individuals", color: "zinc" },
                { name: "Control", price: "$107", desc: "Most popular", color: "amber", highlighted: true },
                { name: "Command", price: "$249", desc: "For teams", color: "zinc" },
              ].map((plan) => (
                <div 
                  key={plan.name} 
                  className={`p-6 text-center ${plan.highlighted ? 'bg-gradient-to-b from-amber-50 to-amber-50/30 relative pt-10' : 'bg-white'}`}
                >
                  {plan.highlighted && (
                    <div className="absolute top-3 left-1/2 -translate-x-1/2">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-1 text-xs font-semibold text-white shadow-sm">
                        <Star className="h-3 w-3 fill-white text-white" />
                        Popular
                      </span>
                    </div>
                  )}
                  <h3 className="font-semibold text-zinc-900 text-lg">{plan.name}</h3>
                  <div className="mt-1">
                    <span className="text-2xl font-bold text-zinc-900">{plan.price}</span>
                    <span className="text-sm text-zinc-500">/mo</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">{plan.desc}</p>
                </div>
              ))}
            </div>

            {/* Feature Categories */}
            <div className="divide-y divide-zinc-100">
              {/* Usage Limits Category */}
              <div>
                <div className="grid grid-cols-4 bg-zinc-50/80">
                  <div className="px-6 py-3">
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Usage & Limits</span>
                  </div>
                  <div className="px-6 py-3" />
                  <div className="px-6 py-3 bg-amber-50/50" />
                  <div className="px-6 py-3" />
                </div>
                {[
                  { feature: "Monthly outputs", node: "10", control: "40", command: "120", tooltip: "Complete deliverables per month" },
                  { feature: "AI Agents", node: "1", control: "2-3", command: "5-8", tooltip: "Concurrent AI workers" },
                  { feature: "Core Users", node: "1", control: "2", command: "5", tooltip: "Full access team members" },
                  { feature: "Lite Users", node: "2", control: "5", command: "Unlimited", tooltip: "View-only access" },
                ].map((row, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="grid grid-cols-4 group hover:bg-zinc-50/50 transition-colors"
                  >
                    <div className="px-6 py-4 flex items-center gap-2">
                      <span className="text-sm text-zinc-700">{row.feature}</span>
                      <div className="relative group/tooltip">
                        <Info className="h-3.5 w-3.5 text-zinc-400 cursor-help" />
                        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 bg-zinc-900 text-white text-xs rounded opacity-0 group-hover/tooltip:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                          {row.tooltip}
                        </div>
                      </div>
                    </div>
                    <div className="px-6 py-4 text-center">
                      <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-zinc-100 text-sm font-semibold text-zinc-900">
                        {row.node}
                      </span>
                    </div>
                    <div className="px-6 py-4 text-center bg-amber-50/30">
                      <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-amber-100 text-sm font-semibold text-amber-700">
                        {row.control}
                      </span>
                    </div>
                    <div className="px-6 py-4 text-center">
                      <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700">
                        {row.command}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* AI Features Category */}
              <div>
                <div className="grid grid-cols-4 bg-zinc-50/80">
                  <div className="px-6 py-3">
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">AI Capabilities</span>
                  </div>
                  <div className="px-6 py-3" />
                  <div className="px-6 py-3 bg-amber-50/50" />
                  <div className="px-6 py-3" />
                </div>
                {[
                  { feature: "Meson (System Builder)", node: false, control: "10/mo", command: "40/mo" },
                  { feature: "Multi-step execution", node: false, control: true, command: true },
                  { feature: "Custom agent training", node: false, control: false, command: true },
                  { feature: "Cross-department agents", node: false, control: false, command: true },
                ].map((row, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="grid grid-cols-4 group hover:bg-zinc-50/50 transition-colors"
                  >
                    <div className="px-6 py-4">
                      <span className="text-sm text-zinc-700">{row.feature}</span>
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {typeof row.node === 'boolean' ? (
                        row.node ? (
                          <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                            <Check className="h-4 w-4 text-emerald-600" />
                          </div>
                        ) : (
                          <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                            <Minus className="h-4 w-4 text-zinc-400" />
                          </div>
                        )
                      ) : (
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-full bg-zinc-100 text-sm font-semibold text-zinc-900">
                          {row.node}
                        </span>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                      {typeof row.control === 'boolean' ? (
                        row.control ? (
                          <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                            <Check className="h-4 w-4 text-emerald-600" />
                          </div>
                        ) : (
                          <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                            <Minus className="h-4 w-4 text-zinc-400" />
                          </div>
                        )
                      ) : (
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-full bg-amber-100 text-sm font-semibold text-amber-700">
                          {row.control}
                        </span>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {typeof row.command === 'boolean' ? (
                        row.command ? (
                          <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                            <Check className="h-4 w-4 text-emerald-600" />
                          </div>
                        ) : (
                          <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                            <Minus className="h-4 w-4 text-zinc-400" />
                          </div>
                        )
                      ) : (
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700">
                          {row.command}
                        </span>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Integrations Category */}
              <div>
                <div className="grid grid-cols-4 bg-zinc-50/80">
                  <div className="px-6 py-3">
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Integrations & Delivery</span>
                  </div>
                  <div className="px-6 py-3" />
                  <div className="px-6 py-3 bg-amber-50/50" />
                  <div className="px-6 py-3" />
                </div>
                {[
                  { feature: "Email delivery", node: true, control: true, command: true },
                  { feature: "Slack delivery", node: false, control: true, command: true },
                  { feature: "CRM + Outlook integrations", node: false, control: true, command: true },
                  { feature: "Advanced integrations", node: false, control: false, command: true },
                ].map((row, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="grid grid-cols-4 group hover:bg-zinc-50/50 transition-colors"
                  >
                    <div className="px-6 py-4">
                      <span className="text-sm text-zinc-700">{row.feature}</span>
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {row.node ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                      {row.control ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {row.command ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Support Category */}
              <div>
                <div className="grid grid-cols-4 bg-zinc-50/80">
                  <div className="px-6 py-3">
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Support & Collaboration</span>
                  </div>
                  <div className="px-6 py-3" />
                  <div className="px-6 py-3 bg-amber-50/50" />
                  <div className="px-6 py-3" />
                </div>
                {[
                  { feature: "Community support", node: true, control: true, command: true },
                  { feature: "Priority support", node: false, control: true, command: true },
                  { feature: "Dedicated support", node: false, control: false, command: true },
                  { feature: "Team collaboration workspace", node: false, control: false, command: true },
                  { feature: "Approvals + workflows", node: false, control: false, command: true },
                ].map((row, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="grid grid-cols-4 group hover:bg-zinc-50/50 transition-colors"
                  >
                    <div className="px-6 py-4">
                      <span className="text-sm text-zinc-700">{row.feature}</span>
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {row.node ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                      {row.control ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                    <div className="px-6 py-4 flex justify-center">
                      {row.command ? (
                        <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
                          <Check className="h-4 w-4 text-emerald-600" />
                        </div>
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center">
                          <Minus className="h-4 w-4 text-zinc-400" />
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* CTA Row */}
            <div className="grid grid-cols-4 border-t border-zinc-200 bg-zinc-50/50">
              <div className="p-6" />
              {[
                { name: "Node", highlighted: false },
                { name: "Control", highlighted: true },
                { name: "Command", highlighted: false },
              ].map((plan) => (
                <div key={plan.name} className={`p-6 text-center ${plan.highlighted ? 'bg-amber-50/50' : ''}`}>
                  <Link
                    href="/get-started"
                    className={`inline-flex items-center justify-center gap-2 rounded-full px-6 py-2.5 text-sm font-semibold transition-all ${
                      plan.highlighted
                        ? "bg-zinc-900 text-white hover:bg-zinc-800 shadow-lg shadow-zinc-900/20"
                        : "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50 hover:border-zinc-400"
                    }`}
                  >
                    Get started
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Trust Badges */}
      <section className="relative py-16 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid sm:grid-cols-4 gap-6">
            {[
              { icon: Shield, title: "Enterprise-grade security", description: "SOC 2 compliant" },
              { icon: Clock, title: "7-day free trial", description: "No credit card required" },
              { icon: RefreshCcw, title: "Cancel anytime", description: "No long-term contracts" },
              { icon: BadgeCheck, title: "Money-back guarantee", description: "30-day refund policy" },
            ].map((badge, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="text-center"
              >
                <div className="mx-auto h-12 w-12 rounded-xl bg-zinc-100 flex items-center justify-center mb-3">
                  <badge.icon className="h-6 w-6 text-zinc-600" />
                </div>
                <p className="font-medium text-zinc-900 text-sm">{badge.title}</p>
                <p className="text-xs text-zinc-500 mt-1">{badge.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-3xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              Frequently asked questions
            </h2>
          </motion.div>

          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-2xl border border-zinc-200 bg-white overflow-hidden shadow-sm"
              >
                <button
                  onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                  className="w-full flex items-center justify-between p-6 text-left hover:bg-zinc-50 transition-colors"
                >
                  <span className="font-medium text-zinc-900 pr-4">{faq.question}</span>
                  <motion.div
                    animate={{ rotate: expandedFaq === i ? 90 : 0 }}
                    className="shrink-0 h-6 w-6 rounded-full bg-zinc-100 flex items-center justify-center"
                  >
                    <ChevronRight className="h-4 w-4 text-zinc-500" />
                  </motion.div>
                </button>
                <AnimatePresence>
                  {expandedFaq === i && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <div className="px-6 pb-6 text-sm text-zinc-600 leading-relaxed">
                        {faq.answer}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative py-24 border-t border-zinc-200 bg-white">
        <div className="absolute inset-0 bg-gradient-to-t from-amber-50 via-transparent to-transparent" />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-amber-100 rounded-full blur-3xl opacity-40" />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center"
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-900">
              Put your work on autopilot.
            </h2>
            <p className="mt-4 text-zinc-600">
              See complete outputs in minutes.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800 shadow-lg shadow-zinc-900/20"
              >
                Start your 7-day free trial
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
            <p className="mt-4 text-sm text-zinc-500">
              No credit card required. Full access for 7 days.
            </p>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
