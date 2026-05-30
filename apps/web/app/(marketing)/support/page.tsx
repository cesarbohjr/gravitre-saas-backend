"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  Search, 
  BookOpen, 
  MessageSquare, 
  Mail, 
  ArrowRight,
  HelpCircle,
  Zap,
  Shield,
  Database,
  Users,
  CreditCard
} from "lucide-react"

const categories = [
  {
    icon: Zap,
    title: "Getting Started",
    description: "Setup guides and quickstarts",
    articles: 12,
    href: "/support/getting-started",
  },
  {
    icon: Users,
    title: "Account & Billing",
    description: "Manage your subscription and team",
    articles: 8,
    href: "/support/account",
  },
  {
    icon: Database,
    title: "Integrations",
    description: "Connect your tools and data",
    articles: 24,
    href: "/support/integrations",
  },
  {
    icon: Shield,
    title: "Security & Compliance",
    description: "Privacy, security, and compliance",
    articles: 10,
    href: "/support/security",
  },
  {
    icon: HelpCircle,
    title: "Troubleshooting",
    description: "Common issues and solutions",
    articles: 18,
    href: "/support/troubleshooting",
  },
  {
    icon: CreditCard,
    title: "API & Developers",
    description: "Technical documentation",
    articles: 15,
    href: "/support/api",
  },
]

const popularArticles = [
  { title: "How to create your first agent", views: "12.4k" },
  { title: "Connecting to Salesforce", views: "8.2k" },
  { title: "Understanding workflow triggers", views: "7.1k" },
  { title: "Managing team permissions", views: "5.8k" },
  { title: "Troubleshooting sync errors", views: "5.2k" },
  { title: "Setting up SSO/SAML", views: "4.9k" },
]

const faqs = [
  {
    question: "What is Gravitre?",
    answer: "Gravitre is an AI-powered operations platform that helps businesses automate workflows, deploy AI agents, and orchestrate complex business processes.",
  },
  {
    question: "How do I get started?",
    answer: "Sign up for a free 7-day trial, complete the onboarding wizard, and you'll be guided through creating your first agent and workflow.",
  },
  {
    question: "What integrations are supported?",
    answer: "We support 50+ integrations including Salesforce, HubSpot, Slack, Google Workspace, Microsoft 365, Notion, and many more. View our full integrations list.",
  },
  {
    question: "Is my data secure?",
    answer: "Yes. Gravitre uses AES-256 encryption for all data at rest and in transit, with role-based access control and complete audit trails.",
  },
  {
    question: "Can I cancel anytime?",
    answer: "Yes, you can cancel your subscription at any time. Your access continues until the end of your current billing period.",
  },
]

export default function SupportPage() {
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
              How can we help?
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Find answers, explore guides, and get support from our team.
            </p>
            
            {/* Search */}
            <div className="mt-8 max-w-xl mx-auto">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search for help..."
                  className="w-full rounded-xl border border-zinc-300 bg-white pl-12 pr-4 py-4 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Categories */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categories.map((category, i) => {
              const Icon = category.icon
              return (
                <motion.a
                  key={category.title}
                  href={category.href}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="group rounded-xl border border-zinc-200 bg-white p-6 transition-all hover:border-emerald-300 hover:shadow-md"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 mb-4">
                    <Icon className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h3 className="font-medium text-zinc-900 group-hover:text-emerald-600 transition-colors">
                    {category.title}
                  </h3>
                  <p className="text-sm text-zinc-500 mt-1">{category.description}</p>
                  <span className="text-xs text-zinc-400 mt-2 block">{category.articles} articles</span>
                </motion.a>
              )
            })}
          </div>
        </div>
      </section>

      {/* Popular Articles */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <h2 className="text-2xl font-semibold text-zinc-900">Popular Articles</h2>
          </motion.div>
          <div className="space-y-2">
            {popularArticles.map((article, i) => (
              <motion.a
                key={article.title}
                href={`/docs/guides/${article.title.toLowerCase().replace(/\s+/g, '-')}`}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-zinc-300 hover:shadow-sm"
              >
                <span className="text-sm text-zinc-900">{article.title}</span>
                <span className="text-xs text-zinc-500">{article.views} views</span>
              </motion.a>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Frequently Asked Questions</h2>
          </motion.div>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <motion.div
                key={faq.question}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm"
              >
                <h3 className="font-medium text-zinc-900 mb-2">{faq.question}</h3>
                <p className="text-sm text-zinc-600">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact Options */}
      <section className="px-6 py-16 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Still need help?</h2>
            <p className="text-zinc-600">Our team is ready to assist you.</p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-3">
            <motion.a
              href="/contact"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="group rounded-xl border border-zinc-200 bg-white p-6 text-center transition-all hover:border-emerald-300 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 mb-4">
                <Mail className="h-5 w-5 text-emerald-600" />
              </div>
              <h3 className="font-medium text-zinc-900 mb-1">Email Support</h3>
              <p className="text-sm text-zinc-500">Response within 24 hours</p>
            </motion.a>
            <motion.button
              onClick={() => window.open('https://gravitre.com/chat', '_blank')}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="group rounded-xl border border-zinc-200 bg-white p-6 text-center transition-all hover:border-emerald-300 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 mb-4">
                <MessageSquare className="h-5 w-5 text-emerald-600" />
              </div>
              <h3 className="font-medium text-zinc-900 mb-1">Live Chat</h3>
              <p className="text-sm text-zinc-500">Available 9am-6pm PT</p>
            </motion.button>
            <motion.a
              href="/docs"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
              className="group rounded-xl border border-zinc-200 bg-white p-6 text-center transition-all hover:border-emerald-300 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 mb-4">
                <BookOpen className="h-5 w-5 text-emerald-600" />
              </div>
              <h3 className="font-medium text-zinc-900 mb-1">Documentation</h3>
              <p className="text-sm text-zinc-500">Technical guides & API docs</p>
            </motion.a>
          </div>
        </div>
      </section>
    </div>
  )
}
