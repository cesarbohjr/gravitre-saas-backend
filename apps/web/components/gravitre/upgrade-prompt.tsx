"use client"

import { motion, AnimatePresence } from "framer-motion"
import { 
  Blocks, 
  X, 
  ArrowRight, 
  Check,
  Sparkles,
  Zap,
  Crown
} from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"

interface UpgradePromptProps {
  open: boolean
  onClose: () => void
  feature: "meson" | "agents" | "outputs" | "integrations"
  currentPlan?: "node" | "control" | "command"
}

const featureDetails = {
  meson: {
    title: "Meson",
    icon: Blocks,
    description: "Build agents, training, and workflows from a single request.",
    color: "violet",
    gradient: "from-violet-500 to-purple-500",
    requiredPlans: ["control", "command"],
    benefits: [
      "Create agents automatically",
      "Generate training structures",
      "Build workflows in seconds",
      "Deploy immediately"
    ]
  },
  agents: {
    title: "More Agents",
    icon: Sparkles,
    description: "Scale your AI workforce with additional agent capacity.",
    color: "blue",
    gradient: "from-blue-500 to-indigo-500",
    requiredPlans: ["control", "command"],
    benefits: [
      "Run multiple agents simultaneously",
      "Department-specific agents",
      "Cross-team collaboration",
      "Specialized workflows"
    ]
  },
  outputs: {
    title: "More Outputs",
    icon: Zap,
    description: "Increase your monthly output capacity for more work.",
    color: "emerald",
    gradient: "from-emerald-500 to-teal-500",
    requiredPlans: ["control", "command"],
    benefits: [
      "Higher monthly limits",
      "Burst capacity",
      "Priority processing",
      "Pay-as-you-go options"
    ]
  },
  integrations: {
    title: "Advanced Integrations",
    icon: Crown,
    description: "Connect to enterprise tools and advanced data sources.",
    color: "amber",
    gradient: "from-amber-500 to-orange-500",
    requiredPlans: ["command"],
    benefits: [
      "Enterprise CRM systems",
      "Data warehouse connections",
      "Custom API integrations",
      "SSO and security features"
    ]
  }
}

const planUpgrades = {
  node: {
    recommendedPlan: "Control",
    price: "$129/month",
    highlight: "Includes Meson access"
  },
  control: {
    recommendedPlan: "Command",
    price: "$299/month",
    highlight: "Unlimited team scale"
  },
  command: {
    recommendedPlan: "Enterprise",
    price: "Custom",
    highlight: "Contact sales"
  }
}

export function UpgradePrompt({ open, onClose, feature, currentPlan = "node" }: UpgradePromptProps) {
  const featureInfo = featureDetails[feature]
  const upgradeInfo = planUpgrades[currentPlan]
  const Icon = featureInfo.icon

  if (!open) return null

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
        >
          {/* Header with gradient */}
          <div className={`relative p-6 bg-gradient-to-br ${featureInfo.gradient} bg-opacity-10`}
            style={{ background: `linear-gradient(to bottom right, rgb(${featureInfo.color === 'violet' ? '139 92 246' : featureInfo.color === 'blue' ? '59 130 246' : featureInfo.color === 'emerald' ? '16 185 129' : '245 158 11'} / 0.1), transparent)` }}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 h-8 w-8 rounded-lg hover:bg-secondary flex items-center justify-center transition-colors"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>

            <div className={`h-14 w-14 rounded-2xl bg-gradient-to-br ${featureInfo.gradient} flex items-center justify-center mb-4`}>
              <Icon className="h-7 w-7 text-white" />
            </div>
            
            <h2 className="text-xl font-semibold text-foreground">
              {featureInfo.title} is available in {upgradeInfo.recommendedPlan}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {featureInfo.description}
            </p>
          </div>

          {/* Benefits */}
          <div className="p-6 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              What you get
            </p>
            <ul className="space-y-3">
              {featureInfo.benefits.map((benefit, i) => (
                <li key={i} className="flex items-center gap-3">
                  <div className={`h-5 w-5 rounded-full bg-gradient-to-br ${featureInfo.gradient} flex items-center justify-center`}>
                    <Check className="h-3 w-3 text-white" />
                  </div>
                  <span className="text-sm text-foreground">{benefit}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Upgrade CTA */}
          <div className="p-6 bg-secondary/30 border-t border-border">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-sm font-medium text-foreground">{upgradeInfo.recommendedPlan}</p>
                <p className="text-xs text-muted-foreground">{upgradeInfo.highlight}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold text-foreground">{upgradeInfo.price}</p>
              </div>
            </div>
            
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={onClose}>
                Maybe later
              </Button>
              <Button asChild className={`flex-1 bg-gradient-to-r ${featureInfo.gradient} hover:opacity-90`}>
                <Link href="/pricing">
                  Upgrade now
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}

// Hook to check feature access
export function useFeatureAccess(userPlan: "node" | "control" | "command" = "node") {
  const canAccessMeson = userPlan === "control" || userPlan === "command"
  const canAccessAdvancedIntegrations = userPlan === "command"
  
  const mesonLimit = userPlan === "control" ? 10 : userPlan === "command" ? 40 : 0
  const agentLimit = userPlan === "node" ? 1 : userPlan === "control" ? 3 : 8
  const outputLimit = userPlan === "node" ? 10 : userPlan === "control" ? 40 : 120
  const coreUserLimit = userPlan === "node" ? 1 : userPlan === "control" ? 2 : 5
  const liteUserLimit = userPlan === "node" ? 2 : userPlan === "control" ? 5 : -1 // -1 = unlimited

  return {
    canAccessMeson,
    canAccessAdvancedIntegrations,
    mesonLimit,
    agentLimit,
    outputLimit,
    coreUserLimit,
    liteUserLimit,
    plan: userPlan
  }
}

// Wrapper component for feature-gated content
interface FeatureGateProps {
  feature: "meson" | "agents" | "outputs" | "integrations"
  userPlan?: "node" | "control" | "command"
  children: React.ReactNode
  fallback?: React.ReactNode
}

export function FeatureGate({ feature, userPlan = "node", children, fallback }: FeatureGateProps) {
  const access = useFeatureAccess(userPlan)
  
  const hasAccess = () => {
    switch (feature) {
      case "meson":
        return access.canAccessMeson
      case "integrations":
        return access.canAccessAdvancedIntegrations
      default:
        return true
    }
  }

  if (hasAccess()) {
    return <>{children}</>
  }

  return fallback ? <>{fallback}</> : null
}
