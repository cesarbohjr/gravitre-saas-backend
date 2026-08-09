import {
  Zap,
  Play,
  FileText,
  Send,
  Users,
  Crown,
  Smartphone,
  Monitor,
  Building2,
  Rocket,
  Blocks,
  Globe,
} from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_RESEARCH_LOOKUPS_PRICING } from "@/lib/marketing-flags"
import {
  formatResearchLookupOveragePrice,
  researchLookupsIncludedLabel,
} from "@/lib/internet-research-pricing"
import { PLAN_CATALOG, type PlanCode } from "@/lib/plans"

export type PlanComparisonCell = boolean | string

export type PlanComparisonRow = {
  feature: string
  node: PlanComparisonCell
  control: PlanComparisonCell
  command: PlanComparisonCell
}

function planPrices(code: PlanCode) {
  const plan = PLAN_CATALOG[code]
  return { monthly: plan.price ?? 0, annual: plan.annualPrice ?? 0 }
}

export const roles = {
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
} as const

export type RoleKey = keyof typeof roles

export const tiers = [
  {
    name: "Node",
    planCode: "node" as const,
    tagline: "Focused execution for small teams",
    price: planPrices("node"),
    description: "Generate complete outputs like campaigns, reports, or workflows—without building everything from scratch.",
    outputs: "Up to 10 complete outputs / month",
    team: {
      agents: "1 Agent",
      coreUsers: "1 Core User",
      liteUsers: "2 Lite Users",
    },
    meson: null,
    features: [
      "Voice included — Text | Voice in chat",
      "Email delivery",
      "Basic campaign outputs",
      "3 app integrations",
      "Insights & connector health",
      "Community support",
      ...(SHOW_RESEARCH_LOOKUPS_PRICING
        ? [researchLookupsIncludedLabel("node") || "10 research lookups / month"]
        : []),
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
    planCode: "control" as const,
    tagline: "Coordinate work across your systems",
    price: planPrices("control"),
    description: "Plan and execute multi-step work across email, CRM, and data sources with full campaign capabilities.",
    outputs: "Up to 40 complete outputs / month",
    team: {
      agents: "2-3 Agents",
      coreUsers: "2 Core Users",
      liteUsers: "5 Lite Users",
    },
    meson: { count: 10, label: "10 Mesons / month" },
    features: [
      "Voice included — Text | Voice in chat",
      "CRM + Outlook integrations",
      "Multi-step execution",
      "Learning admin (GIBE)",
      "Failure predictions",
      "Full campaign outputs",
      "Slack delivery",
      "Priority support",
      ...(SHOW_RESEARCH_LOOKUPS_PRICING
        ? [researchLookupsIncludedLabel("control") || "60 research lookups / month"]
        : []),
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
    planCode: "command" as const,
    tagline: "Run AI agents across your entire team",
    price: planPrices("command"),
    description: "Deploy multiple agents that collaborate, execute, and deliver work across your organization.",
    outputs: "Up to 120 complete outputs / month",
    team: {
      agents: "5-8 Agents",
      coreUsers: "5 Core Users",
      liteUsers: "Unlimited Lite Users",
    },
    meson: { count: 40, label: "40 Mesons / month" },
    features: [
      "Voice included — Text | Voice in chat",
      "Approvals + workflows",
      "Predictive ops packs",
      "Advanced integrations",
      "Team collaboration workspace",
      "Cross-department agents",
      "Model registry & training",
      "Dedicated support",
      ...(SHOW_RESEARCH_LOOKUPS_PRICING
        ? [researchLookupsIncludedLabel("command") || "200 research lookups / month"]
        : []),
    ],
    cta: "Start 7-day free trial",
    highlighted: false,
    color: "blue",
    gradient: "from-blue-500 to-indigo-500",
    glow: "blue-500/20",
    icon: Rocket,
  },
] as const

export type PricingTier = (typeof tiers)[number]

export const addOns = [
  {
    name: "Additional Core Users",
    price: "$29/month each",
    description: "Add more builders and configurers to your team",
    icon: Users,
  },
  {
    name: "Additional Outputs",
    price: "$1.50–$2.50 each",
    description: "Node $2.50 · Control $2.00 · Command $1.50 per output above plan allotment",
    icon: Zap,
  },
  {
    name: "Additional Mesons",
    price: "$2.00–$3.00 each",
    description: "Control $3.00 · Command $2.00 per Meson above plan allotment",
    icon: Blocks,
  },
  ...(SHOW_RESEARCH_LOOKUPS_PRICING
    ? [
        {
          name: "Additional Research Lookups",
          price: formatResearchLookupOveragePrice(),
          description: "Live internet research lookups above your plan allotment",
          icon: Globe,
        },
      ]
    : []),
]

export const faqs = [
  ...(SHOW_RESEARCH_LOOKUPS_PRICING
    ? [
        {
          question: "What is an internet research lookup?",
          answer:
            "A research lookup is one live web search Gravitre runs when you ask for current external information — for example via assistant web search or the adaptive research cascade. Each plan includes a monthly allotment; lookups above that are billed at " +
            formatResearchLookupOveragePrice() +
            ".",
        },
      ]
    : []),
  {
    question: "Is voice included, or is it an add-on?",
    answer:
      "Voice is included on every plan — switch Text | Voice in chat for spoken replies. Comparable automation platforms often sell voice or AI agents as paid add-ons; we include the capability in Node, Control, and Command.",
  },
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
    answer: "You get 7 days of full access to your chosen plan. If you don't subscribe, your workspace pauses—nothing gets deleted.",
  },
  {
    question: "What happens after I hit my limit?",
    answer: SHOW_RESEARCH_LOOKUPS_PRICING
      ? `We notify you as you approach your limits. Additional outputs are $2.50 (Node), $2.00 (Control), or $1.50 (Command) each. Internet research lookups above your plan allotment are billed at ${formatResearchLookupOveragePrice()}. Upgrade anytime for more included capacity.`
      : "We'll notify you as you approach your limit. Additional outputs are $2.50 (Node), $2.00 (Control), or $1.50 (Command) each, or upgrade your plan for more capacity.",
  },
  {
    question: "Can I cancel anytime?",
    answer: "Yes. Cancel anytime from your settings. Your access continues until the end of your billing period. No penalties, no hassle.",
  },
  {
    question: "Do agents learn my business?",
    answer: MARKETING_COPY.pricing.faqLearning,
  },
  {
    question: "Can agents be shared across departments?",
    answer: "Yes. Agents can be configured per department or shared across teams. Command plan includes cross-department agent capabilities for organization-wide workflows.",
  },
  {
    question: "What is Meson?",
    answer: MARKETING_COPY.pricing.faqMeson,
  },
  {
    question: "How do Mesons work?",
    answer: "A Meson is one system-building request. You describe what you want to create (an agent, workflow, or training setup), and Meson generates everything you need. Usage is only triggered when you click 'Run Meson'—not while typing or exploring.",
  },
]

export const howItWorks = [
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

export const aiCapabilityRows: PlanComparisonRow[] = [
  {
    feature: "Voice in chat (Text | Voice)",
    node: "Included",
    control: "Included",
    command: "Included",
  },
  { feature: "Meson (System Builder)", node: false, control: "10/mo", command: "40/mo" },
  { feature: "Multi-step execution", node: false, control: true, command: true },
  { feature: "Custom agent training", node: false, control: false, command: true },
  { feature: "Cross-department agents", node: false, control: false, command: true },
  ...(SHOW_RESEARCH_LOOKUPS_PRICING
    ? [
        {
          feature: "Internet research lookups / month",
          node: "10 included",
          control: "60 included",
          command: "200 included",
        },
        {
          feature: "Research lookup overage",
          node: formatResearchLookupOveragePrice(),
          control: formatResearchLookupOveragePrice(),
          command: formatResearchLookupOveragePrice(),
        },
      ]
    : []),
  ...MARKETING_COPY.pricing.intelligenceRows,
]
