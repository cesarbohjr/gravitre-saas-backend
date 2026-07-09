"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  ArrowRight, 
  Clock, 
  BookOpen,
  Zap,
  Bot,
  Workflow,
  Database,
  Shield,
  Code,
  Users,
  Lightbulb,
  TrendingUp,
  Settings,
  Play,
  Filter
} from "lucide-react"
import { useState } from "react"

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
    description: "Deep dive into what AI agents can do: data analysis, content generation, decision making, and more.",
    category: "agents",
    difficulty: "Intermediate",
    time: "15 min",
    featured: true,
    image: "/images/guide-capabilities.jpg",
  },
  {
    title: "Building Multi-Step Workflows",
    description: "Create sophisticated automation workflows that chain multiple agents and actions together.",
    category: "workflows",
    difficulty: "Intermediate",
    time: "20 min",
    featured: true,
    image: "/images/guide-workflows.jpg",
  },
  {
    title: "Connecting Salesforce CRM",
    description: "Step-by-step guide to integrating Gravitre with your Salesforce instance for sales automation.",
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
    description: "Implement robust error handling, retries, and fallback strategies in your workflows.",
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
  Beginner: "text-emerald-700 bg-emerald-100",
  Intermediate: "text-amber-700 bg-amber-100",
  Advanced: "text-purple-700 bg-purple-100",
}

export default function GuidesPage() {
  const [activeCategory, setActiveCategory] = useState("all")
  
  const filteredGuides = activeCategory === "all" 
    ? guides 
    : guides.filter(g => g.category === activeCategory)
  
  const featuredGuides = guides.filter(g => g.featured)

  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-emerald-100/50 rounded-full blur-3xl" />
        
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 mb-6">
              <BookOpen className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">Learning Resources</span>
            </div>
            
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl">
              Guides & Tutorials
            </h1>
            
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Step-by-step tutorials to help you master Gravitre. From your first agent 
              to advanced automation patterns.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Featured Guides */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <h2 className="text-2xl font-bold text-zinc-900">Featured Guides</h2>
          </motion.div>
          
          <div className="grid gap-6 md:grid-cols-3">
            {featuredGuides.map((guide, i) => (
              <motion.a
                key={guide.title}
                href={`/guides/${guide.title.toLowerCase().replace(/\s+/g, '-')}`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group relative overflow-hidden rounded-2xl border border-zinc-200 bg-white transition-all hover:border-emerald-300 hover:shadow-lg"
              >
                <div className="aspect-video bg-gradient-to-br from-emerald-50 via-white to-zinc-50 p-6 flex items-center justify-center">
                  <div className="h-16 w-16 rounded-2xl bg-zinc-100 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Play className="h-8 w-8 text-zinc-600" />
                  </div>
                </div>
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyColors[guide.difficulty]}`}>
                      {guide.difficulty}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-zinc-500">
                      <Clock className="h-3 w-3" />
                      {guide.time}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900 group-hover:text-emerald-600 transition-colors mb-2">
                    {guide.title}
                  </h3>
                  <p className="text-sm text-zinc-500 line-clamp-2">{guide.description}</p>
                </div>
              </motion.a>
            ))}
          </div>
        </div>
      </section>

      {/* All Guides */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-6xl">
          {/* Category Filter */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex flex-wrap gap-2 mb-8"
          >
            {categories.map((cat) => {
              const Icon = cat.icon
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`
                    inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all
                    ${activeCategory === cat.id 
                      ? 'bg-emerald-600 text-white' 
                      : 'bg-white text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 border border-zinc-200'
                    }
                  `}
                >
                  <Icon className="h-4 w-4" />
                  {cat.label}
                </button>
              )
            })}
          </motion.div>

          {/* Guide Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredGuides.map((guide, i) => (
              <motion.a
                key={guide.title}
                href={`/guides/${guide.title.toLowerCase().replace(/\s+/g, '-')}`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="group p-5 rounded-xl border border-zinc-200 bg-white hover:border-emerald-300 hover:shadow-md transition-all"
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyColors[guide.difficulty]}`}>
                    {guide.difficulty}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-zinc-500">
                    <Clock className="h-3 w-3" />
                    {guide.time}
                  </span>
                </div>
                <h3 className="font-semibold text-zinc-900 group-hover:text-emerald-600 transition-colors mb-2">
                  {guide.title}
                </h3>
                <p className="text-sm text-zinc-500 line-clamp-2">{guide.description}</p>
              </motion.a>
            ))}
          </div>
        </div>
      </section>

      {/* Learning Path */}
      <section className="px-6 py-20 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-zinc-900 mb-4">Recommended Learning Path</h2>
            <p className="text-zinc-600">Follow this path to master Gravitre step by step</p>
          </motion.div>
          
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-8 bottom-8 w-px bg-gradient-to-b from-emerald-500 via-emerald-300 to-transparent hidden sm:block" />
            
            <div className="space-y-6">
              {[
                { step: 1, title: "Set up your workspace", desc: "Configure your team, invite members, set permissions", time: "15 min" },
                { step: 2, title: "Create your first agent", desc: "Build a simple AI agent to understand the basics", time: "10 min" },
                { step: 3, title: "Connect integrations", desc: "Link your tools like Salesforce, Slack, HubSpot", time: "20 min" },
                { step: 4, title: "Build a workflow", desc: "Chain agents and actions into automated workflows", time: "25 min" },
                { step: 5, title: "Monitor and optimize", desc: "Use analytics to improve agent performance", time: "15 min" },
              ].map((item, i) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="flex items-start gap-6"
                >
                  <div className="h-12 w-12 rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center shrink-0 text-emerald-700 font-bold">
                    {item.step}
                  </div>
                  <div className="flex-1 p-5 rounded-xl border border-zinc-200 bg-white shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-zinc-900">{item.title}</h3>
                      <span className="text-xs text-zinc-500">{item.time}</span>
                    </div>
                    <p className="text-sm text-zinc-600">{item.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Video Tutorials */}
      <section className="px-6 py-20 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8 lg:p-12"
          >
            <div className="flex items-center gap-4 mb-6">
              <div className="h-14 w-14 rounded-xl bg-red-100 flex items-center justify-center">
                <Play className="h-7 w-7 text-red-600" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-zinc-900">Video Tutorials</h2>
                <p className="text-zinc-600">Watch and learn from our YouTube channel</p>
              </div>
            </div>
            <p className="text-zinc-600 mb-6">
              Prefer video content? Our YouTube channel has dozens of tutorials, 
              walkthroughs, and tips from the Gravitre team and community.
            </p>
            <a
              href="https://youtube.com/@gravitre"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white hover:bg-red-500 transition-colors"
            >
              Visit YouTube Channel
              <ArrowRight className="h-4 w-4" />
            </a>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-20 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-bold text-zinc-900 mb-4">Ready to get started?</h2>
            <p className="text-zinc-600 mb-8">
              Create your free account and start building with AI agents today.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-8 py-3 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
              >
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-100 transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                Documentation
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
