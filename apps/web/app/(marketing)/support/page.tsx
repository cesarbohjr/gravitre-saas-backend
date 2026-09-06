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
import { SUPPORT_CATEGORY_LINKS, SUPPORT_POPULAR_ARTICLES } from "@/lib/marketing-guide-links"

const categories = [
  {
    icon: Zap,
    title: "Getting Started",
    description: "Setup guides and quickstarts",
    articles: 12,
    href: SUPPORT_CATEGORY_LINKS["Getting Started"],
  },
  {
    icon: Users,
    title: "Account & Billing",
    description: "Manage your subscription and team",
    articles: 8,
    href: SUPPORT_CATEGORY_LINKS["Account & Billing"],
  },
  {
    icon: Database,
    title: "Integrations",
    description: "Connect your tools and data",
    articles: 24,
    href: SUPPORT_CATEGORY_LINKS.Integrations,
  },
  {
    icon: Shield,
    title: "Security & Compliance",
    description: "Privacy, security, and compliance",
    articles: 10,
    href: SUPPORT_CATEGORY_LINKS["Security & Compliance"],
  },
  {
    icon: HelpCircle,
    title: "Troubleshooting",
    description: "Common issues and solutions",
    articles: 18,
    href: SUPPORT_CATEGORY_LINKS.Troubleshooting,
  },
  {
    icon: CreditCard,
    title: "API & Developers",
    description: "Technical documentation",
    articles: 15,
    href: SUPPORT_CATEGORY_LINKS["API & Developers"],
  },
]

const popularArticles = SUPPORT_POPULAR_ARTICLES

const faqs = [
  {
    question: "What is Gravitre?",
    answer: "Gravitre is one AI brain for your business — Gravitre AI, agents, workflows, connectors, approvals, and GIBE learning with human gates on writes.",
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
    <div className="bg-card">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              How can we help?
            </h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
              Find answers, explore guides, and get support from our team.
            </p>
            
            {/* Search */}
            <div className="mt-8 max-w-xl mx-auto">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search for help..."
                  className="w-full rounded-xl border border-border bg-card pl-12 pr-4 py-4 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
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
                  initial={false}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="group rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-md"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-4">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-medium text-foreground group-hover:text-primary transition-colors">
                    {category.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1">{category.description}</p>
                  <span className="text-xs text-muted-foreground mt-2 block">{category.articles} articles</span>
                </motion.a>
              )
            })}
          </div>
        </div>
      </section>

      {/* Popular Articles */}
      <section className="px-6 py-16 border-t border-border">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.15 }}
            className="mb-8"
          >
            <h2 className="text-2xl font-semibold text-foreground">Popular Articles</h2>
          </motion.div>
          <div className="space-y-2">
            {popularArticles.map((article, i) => (
              <motion.a
                key={article.title}
                href={article.href}
                initial={false}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.15 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-all hover:border-border hover:shadow-sm"
              >
                <span className="text-sm text-foreground">{article.title}</span>
                <span className="text-xs text-muted-foreground">{article.views} views</span>
              </motion.a>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="px-6 py-16 border-t border-border">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.15 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-foreground mb-4">Frequently Asked Questions</h2>
          </motion.div>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <motion.div
                key={faq.question}
                initial={false}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.15 }}
                transition={{ delay: i * 0.05 }}
                className="rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <h3 className="font-medium text-foreground mb-2">{faq.question}</h3>
                <p className="text-sm text-muted-foreground">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact Options */}
      <section className="px-6 py-16 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.15 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-foreground mb-4">Still need help?</h2>
            <p className="text-muted-foreground">Our team is ready to assist you.</p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-3">
            <motion.a
              href="/contact"
              initial={false}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.15 }}
              className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <Mail className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Email Support</h3>
              <p className="text-sm text-muted-foreground">Response within 24 hours</p>
            </motion.a>
            <motion.a
              href="/contact"
              initial={false}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ delay: 0.1 }}
              className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <MessageSquare className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Live Chat</h3>
              <p className="text-sm text-muted-foreground">Available 9am-6pm PT</p>
            </motion.a>
            <motion.a
              href="/docs"
              initial={false}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.15 }}
              transition={{ delay: 0.2 }}
              className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md"
            >
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Documentation</h3>
              <p className="text-sm text-muted-foreground">Technical guides & API docs</p>
            </motion.a>
          </div>
        </div>
      </section>
    </div>
  )
}
