"use client"

import Link from "next/link"
import {
  ArrowRight,
  Clock,
  BookOpen,
  Zap,
  Bot,
  Workflow,
  Database,
  Lightbulb,
  Play,
} from "lucide-react"
import { useState } from "react"
import { guideHref } from "@/lib/marketing-guide-links"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageEndCta,
  MarketingPageHero,
  MarketingRails,
} from "@/components/marketing/nodus/page-shell"
import {
  GUIDES_TRACE_STAGES,
  GravitreFlow,
  GravitreReveal,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system"

const categories = [
  { id: "all", label: "All Guides", icon: BookOpen },
  { id: "getting-started", label: "Getting Started", icon: Zap },
  { id: "agents", label: "AI Agents", icon: Bot },
  { id: "workflows", label: "Workflows", icon: Workflow },
  { id: "integrations", label: "Integrations", icon: Database },
  { id: "best-practices", label: "Best Practices", icon: Lightbulb },
]

const guides = [
  {
    title: "Install the Chrome browser extension",
    description:
      "Install → connect → enrich a page → approve a write → see it in Outcomes. Same catalog governance as chat.",
    category: "getting-started",
    difficulty: "Beginner",
    time: "12 min",
    featured: true,
    image: "/images/guide-first-agent.jpg",
  },
  {
    title: "Create Your First AI Agent",
    description: "Learn how to set up, configure, and deploy your first AI agent in under 10 minutes.",
    category: "getting-started",
    difficulty: "Beginner",
    time: "10 min",
    featured: true,
    image: "/images/guide-first-agent.jpg",
  },
  {
    title: "Understanding Agent Capabilities",
    description:
      "Deep dive into what AI agents can do: data analysis, content generation, decision making, and more.",
    category: "agents",
    difficulty: "Intermediate",
    time: "15 min",
    featured: true,
    image: "/images/guide-capabilities.jpg",
  },
  {
    title: "Building Multi-Step Workflows",
    description:
      "Create sophisticated automation workflows that chain multiple agents and actions together.",
    category: "workflows",
    difficulty: "Intermediate",
    time: "20 min",
    featured: true,
    image: "/images/guide-workflows.jpg",
  },
  {
    title: "Connecting Salesforce CRM",
    description:
      "Step-by-step guide to integrating Gravitre with your Salesforce instance for sales automation.",
    category: "integrations",
    difficulty: "Beginner",
    time: "12 min",
    featured: false,
  },
  {
    title: "HubSpot Marketing Automation",
    description: "Automate your marketing workflows by connecting HubSpot to Gravitre agents.",
    category: "integrations",
    difficulty: "Beginner",
    time: "10 min",
    featured: false,
  },
  {
    title: "Slack Notifications & Commands",
    description: "Set up Slack integration for real-time notifications and agent commands.",
    category: "integrations",
    difficulty: "Beginner",
    time: "8 min",
    featured: false,
  },
  {
    title: "Training Agents on Your Brand Voice",
    description: "Teach your AI agents to write in your brand's unique voice and style.",
    category: "agents",
    difficulty: "Intermediate",
    time: "15 min",
    featured: false,
  },
  {
    title: "Setting Up SSO/SAML Authentication",
    description: "Configure single sign-on for enterprise security and compliance requirements.",
    category: "getting-started",
    difficulty: "Advanced",
    time: "20 min",
    featured: false,
  },
  {
    title: "API Quickstart Guide",
    description: "Learn to use the Gravitre API to programmatically trigger agents and workflows.",
    category: "getting-started",
    difficulty: "Intermediate",
    time: "12 min",
    featured: false,
  },
  {
    title: "Workflow Error Handling",
    description:
      "Implement robust error handling, retries, and fallback strategies in your workflows.",
    category: "workflows",
    difficulty: "Advanced",
    time: "18 min",
    featured: false,
  },
  {
    title: "Agent Performance Optimization",
    description: "Tips and techniques for improving agent speed, accuracy, and cost efficiency.",
    category: "best-practices",
    difficulty: "Advanced",
    time: "15 min",
    featured: false,
  },
  {
    title: "Managing Team Permissions",
    description: "Set up role-based access control to manage what team members can see and do.",
    category: "getting-started",
    difficulty: "Beginner",
    time: "8 min",
    featured: false,
  },
  {
    title: "Webhook Integration Patterns",
    description: "Best practices for receiving and handling webhook events from Gravitre.",
    category: "integrations",
    difficulty: "Intermediate",
    time: "14 min",
    featured: false,
  },
  {
    title: "Conditional Logic in Workflows",
    description: "Use branching, conditions, and dynamic routing in your automation workflows.",
    category: "workflows",
    difficulty: "Intermediate",
    time: "12 min",
    featured: false,
  },
  {
    title: "Data Security Best Practices",
    description: "Ensure your data stays secure with encryption, access controls, and audit logging.",
    category: "best-practices",
    difficulty: "Intermediate",
    time: "10 min",
    featured: false,
  },
  {
    title: "Scaling Agent Operations",
    description: "Strategies for scaling from 10 to 10,000 agent runs per day.",
    category: "best-practices",
    difficulty: "Advanced",
    time: "20 min",
    featured: false,
  },
]

const difficultyColors: Record<string, string> = {
  Beginner: "text-primary bg-primary/15",
  Intermediate: "text-amber-700 bg-amber-100",
  Advanced: "text-purple-700 bg-purple-100",
}

const learningPath = [
  {
    step: 1,
    title: "Set up your workspace",
    desc: "Configure your team, invite members, set permissions",
    time: "15 min",
  },
  {
    step: 2,
    title: "Create your first agent",
    desc: "Build a simple AI agent to understand the basics",
    time: "10 min",
  },
  {
    step: 3,
    title: "Connect integrations",
    desc: "Link your tools like Salesforce, Slack, HubSpot",
    time: "20 min",
  },
  {
    step: 4,
    title: "Build a workflow",
    desc: "Chain agents and actions into automated workflows",
    time: "25 min",
  },
  {
    step: 5,
    title: "Monitor and optimize",
    desc: "Use analytics to improve agent performance",
    time: "15 min",
  },
]

export default function GuidesPage() {
  const [activeCategory, setActiveCategory] = useState("all")

  const filteredGuides =
    activeCategory === "all" ? guides : guides.filter((g) => g.category === activeCategory)

  const featuredGuides = guides.filter((g) => g.featured)

  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Learning Resources"
        title="Guides & Tutorials"
        description="Step-by-step tutorials to help you master Gravitre. From your first agent to advanced automation patterns."
      />

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Learning path"
          title="Setup → Agent → Connect → Workflow → Optimize"
          description="One path through the product — follow the stages or jump to the guide you need."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={GUIDES_TRACE_STAGES}
            gradientId="guides-trace"
            ariaLabel="Guides path from Setup through Agent, Connect, and Workflow to Optimize"
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <GravitreReveal className="mb-8">
          <h2 className="text-2xl font-bold text-foreground">Featured Guides</h2>
        </GravitreReveal>

        <div className="grid gap-6 md:grid-cols-3">
          {featuredGuides.map((guide, i) => (
            <GravitreFlow key={guide.title} delay={i * 0.08}>
              <a
                href={guideHref(guide.title)}
                className="group relative block overflow-hidden rounded-2xl border border-border bg-card transition-all hover:border-primary/30 hover:shadow-lg"
              >
                <div className="aspect-video bg-gradient-to-br from-primary/10 via-white to-muted/50 p-6 flex items-center justify-center">
                  <div className="h-16 w-16 rounded-2xl bg-muted flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Play className="h-8 w-8 text-muted-foreground" />
                  </div>
                </div>
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyColors[guide.difficulty]}`}
                    >
                      {guide.difficulty}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {guide.time}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors mb-2">
                    {guide.title}
                  </h3>
                  <p className="text-sm text-muted-foreground line-clamp-2">{guide.description}</p>
                </div>
              </a>
            </GravitreFlow>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="flex flex-wrap gap-2 mb-8">
          {categories.map((cat) => {
            const Icon = cat.icon
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`
                    inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all
                    ${
                      activeCategory === cat.id
                        ? "bg-primary text-white"
                        : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground border border-border"
                    }
                  `}
              >
                <Icon className="h-4 w-4" />
                {cat.label}
              </button>
            )
          })}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredGuides.map((guide, i) => (
            <GravitreFlow key={guide.title} delay={i * 0.05}>
              <a
                href={guideHref(guide.title)}
                className="group block p-5 rounded-xl border border-border bg-card hover:border-primary/30 hover:shadow-md transition-all"
              >
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyColors[guide.difficulty]}`}
                  >
                    {guide.difficulty}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {guide.time}
                  </span>
                </div>
                <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors mb-2">
                  {guide.title}
                </h3>
                <p className="text-sm text-muted-foreground line-clamp-2">{guide.description}</p>
              </a>
            </GravitreFlow>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="text-center mb-12">
            <h2 className="text-3xl font-bold text-foreground mb-4">Recommended Learning Path</h2>
            <p className="text-muted-foreground">Follow this path to master Gravitre step by step</p>
          </GravitreReveal>

          <div className="relative">
            <div className="absolute left-6 top-8 bottom-8 w-px bg-gradient-to-b from-primary/100 via-emerald-300 to-transparent hidden sm:block" />

            <div className="space-y-6">
              {learningPath.map((item, i) => (
                <GravitreFlow key={item.step} delay={i * 0.08} className="flex items-start gap-6">
                  <div className="h-12 w-12 rounded-full bg-primary/15 border border-primary/20 flex items-center justify-center shrink-0 text-primary font-bold">
                    {item.step}
                  </div>
                  <div className="flex-1 p-5 rounded-xl border border-border bg-card shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-foreground">{item.title}</h3>
                      <span className="text-xs text-muted-foreground">{item.time}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{item.desc}</p>
                  </div>
                </GravitreFlow>
              ))}
            </div>
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="rounded-2xl border border-border bg-[color:var(--g-marketing-surface)] p-8 lg:p-12">
            <div className="flex items-center gap-4 mb-6">
              <div className="h-14 w-14 rounded-xl bg-muted flex items-center justify-center">
                <BookOpen className="h-7 w-7 text-muted-foreground" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-foreground">Prefer docs?</h2>
                <p className="text-muted-foreground">Written guides live in the documentation hub</p>
              </div>
            </div>
            <p className="text-muted-foreground mb-6">
              Most guides link to published docs pages. Start with the quickstart or browse by topic in the docs.
            </p>
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Browse documentation
              <ArrowRight className="h-4 w-4" />
            </Link>
          </GravitreReveal>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl text-center">
          <GravitreReveal>
            <h2 className="text-3xl font-bold text-foreground mb-4">Ready to get started?</h2>
            <p className="text-muted-foreground mb-8">
              Create an account and start building with AI agents.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-8 py-3 text-sm font-medium text-white hover:bg-primary/90 transition-colors"
              >
                Get started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-8 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                Documentation
              </Link>
            </div>
          </GravitreReveal>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
