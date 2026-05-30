"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  ArrowRight, 
  BookOpen, 
  Code, 
  Zap, 
  Bot, 
  Workflow,
  Database,
  Shield,
  Terminal,
  Search,
  ExternalLink
} from "lucide-react"

const quickLinks = [
  {
    icon: Zap,
    title: "Quickstart",
    description: "Get up and running in under 5 minutes",
    href: "/docs/quickstart",
    color: "text-emerald-600",
  },
  {
    icon: Bot,
    title: "AI Operator",
    description: "Learn how to use natural language automation",
    href: "/docs/ai-operator",
    color: "text-cyan-600",
  },
  {
    icon: Workflow,
    title: "Workflows",
    description: "Build and manage automated workflows",
    href: "/docs/workflows",
    color: "text-purple-600",
  },
  {
    icon: Database,
    title: "Connectors",
    description: "Connect your data sources and tools",
    href: "/docs/connectors",
    color: "text-amber-600",
  },
]

const guides = [
  { title: "Create your first agent", category: "Getting Started", time: "5 min" },
  { title: "Connect Salesforce data", category: "Integrations", time: "10 min" },
  { title: "Build a multi-step workflow", category: "Workflows", time: "15 min" },
  { title: "Set up SSO authentication", category: "Security", time: "10 min" },
  { title: "Use the API to trigger runs", category: "API", time: "8 min" },
  { title: "Configure webhooks", category: "Integrations", time: "5 min" },
]

const sections = [
  {
    title: "Core Concepts",
    icon: BookOpen,
    links: [
      { title: "Introduction", href: "/docs/introduction" },
      { title: "Architecture Overview", href: "/docs/architecture" },
      { title: "Authentication", href: "/docs/authentication" },
      { title: "Workspaces & Teams", href: "/docs/workspaces" },
    ],
  },
  {
    title: "Agents",
    icon: Bot,
    links: [
      { title: "Creating Agents", href: "/docs/agents/creating" },
      { title: "Agent Capabilities", href: "/docs/agents/capabilities" },
      { title: "Agent Versioning", href: "/docs/agents/versioning" },
      { title: "Testing Agents", href: "/docs/agents/testing" },
    ],
  },
  {
    title: "Workflows",
    icon: Workflow,
    links: [
      { title: "Workflow Builder", href: "/docs/workflows/builder" },
      { title: "Triggers & Schedules", href: "/docs/workflows/triggers" },
      { title: "Conditions & Logic", href: "/docs/workflows/conditions" },
      { title: "Error Handling", href: "/docs/workflows/errors" },
    ],
  },
  {
    title: "API Reference",
    icon: Code,
    links: [
      { title: "REST API", href: "/docs/api/rest" },
      { title: "Authentication", href: "/docs/api/auth" },
      { title: "Webhooks", href: "/docs/api/webhooks" },
      { title: "SDKs", href: "/docs/api/sdks" },
    ],
  },
  {
    title: "Security",
    icon: Shield,
    links: [
      { title: "Data Encryption", href: "/docs/security/encryption" },
      { title: "Access Control", href: "/docs/security/access" },
      { title: "Audit Logs", href: "/docs/security/audit" },
      { title: "Compliance", href: "/docs/security/compliance" },
    ],
  },
  {
    title: "Integrations",
    icon: Database,
    links: [
      { title: "Salesforce", href: "/docs/integrations/salesforce" },
      { title: "HubSpot", href: "/docs/integrations/hubspot" },
      { title: "Slack", href: "/docs/integrations/slack" },
      { title: "All Integrations", href: "/docs/integrations" },
    ],
  },
]

export default function DocsPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
              Documentation
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Learn how to integrate, automate, and scale with Gravitre. Start with our quickstart 
              guide or dive into detailed API references.
            </p>
            
            {/* Search */}
            <div className="mt-8 max-w-xl mx-auto">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search documentation..."
                  className="w-full rounded-xl border border-zinc-300 bg-white pl-12 pr-4 py-3.5 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-sm"
                />
                <kbd className="absolute right-4 top-1/2 -translate-y-1/2 hidden sm:inline-flex items-center gap-1 rounded border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-500">
                  <span className="text-xs">Cmd</span>K
                </kbd>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Quick Links */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {quickLinks.map((link, i) => {
              const Icon = link.icon
              return (
                <motion.div
                  key={link.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <Link
                    href={link.href}
                    className="group block rounded-xl border border-zinc-200 bg-white p-5 transition-all hover:border-emerald-300 hover:shadow-md"
                  >
                    <Icon className={`h-6 w-6 ${link.color} mb-3`} />
                    <h3 className="font-medium text-zinc-900 group-hover:text-emerald-700 transition-colors">
                      {link.title}
                    </h3>
                    <p className="text-sm text-zinc-500 mt-1">{link.description}</p>
                  </Link>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Popular Guides */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center justify-between mb-8"
          >
            <h2 className="text-2xl font-semibold text-zinc-900">Popular Guides</h2>
            <Link href="/docs/guides" className="text-sm text-emerald-600 hover:text-emerald-500 flex items-center gap-1">
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {guides.map((guide, i) => (
              <motion.div
                key={guide.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  href="/guides"
                  className="group flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-emerald-300 hover:shadow-sm"
                >
                  <div>
                    <span className="text-xs text-emerald-600">{guide.category}</span>
                    <h3 className="text-sm font-medium text-zinc-900 group-hover:text-emerald-700 transition-colors mt-0.5">
                      {guide.title}
                    </h3>
                  </div>
                  <span className="text-xs text-zinc-400">{guide.time}</span>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Documentation Sections */}
      <section className="px-6 py-16 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-12"
          >
            <h2 className="text-2xl font-semibold text-zinc-900">Browse by Topic</h2>
          </motion.div>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {sections.map((section, i) => {
              const Icon = section.icon
              return (
                <motion.div
                  key={section.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white border border-zinc-200 shadow-sm">
                      <Icon className="h-4 w-4 text-zinc-600" />
                    </div>
                    <h3 className="font-medium text-zinc-900">{section.title}</h3>
                  </div>
                  <ul className="space-y-2">
                    {section.links.map((link) => (
                      <li key={link.title}>
                        <Link
                          href={link.href}
                          className="text-sm text-zinc-600 hover:text-emerald-600 transition-colors"
                        >
                          {link.title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* API & SDKs */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm"
          >
            <div className="flex items-center gap-3 mb-4">
              <Terminal className="h-6 w-6 text-emerald-600" />
              <h2 className="text-xl font-semibold text-zinc-900">API & SDKs</h2>
            </div>
            <p className="text-zinc-600 mb-6">
              Build custom integrations with our REST API or use official SDKs for your preferred language.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/api" className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-900 hover:bg-zinc-100 transition-colors">
                API Reference
                <ExternalLink className="h-3 w-3" />
              </Link>
              <Link href="/docs/quickstart" className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors">
                Node.js SDK
              </Link>
              <Link href="/docs/quickstart" className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors">
                Python SDK
              </Link>
              <Link href="/docs/quickstart" className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors">
                Go SDK
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Help CTA */}
      <section className="px-6 py-16 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Need help?</h2>
            <p className="text-zinc-600 mb-8">
              Can&apos;t find what you&apos;re looking for? Our team is here to help.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
              >
                Contact support
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="https://github.com/gravitre"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100"
              >
                GitHub Discussions
              </a>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
