"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, CheckCircle2, Circle, Clock, ThumbsUp, MessageSquare } from "lucide-react"

const roadmapItems = {
  shipped: [
    {
      title: "Multi-Agent Collaboration",
      description: "Agents can work together on complex tasks with shared context",
      votes: 847,
      comments: 32,
    },
    {
      title: "Workflow Templates Library",
      description: "50+ pre-built templates for common automation use cases",
      votes: 623,
      comments: 18,
    },
    {
      title: "SOC 2 Type II Certification",
      description: "Enterprise-grade security compliance",
      votes: 412,
      comments: 8,
    },
    {
      title: "Advanced Scheduling",
      description: "Cron expressions, time zones, and calendar-aware triggers",
      votes: 389,
      comments: 24,
    },
  ],
  inProgress: [
    {
      title: "Natural Language Workflow Builder",
      description: "Build workflows by describing them in plain English",
      votes: 1247,
      comments: 89,
      progress: 75,
    },
    {
      title: "Custom LLM Integration",
      description: "Bring your own LLM (OpenAI, Anthropic, etc.)",
      votes: 934,
      comments: 56,
      progress: 60,
    },
    {
      title: "Mobile App",
      description: "Monitor and manage workflows from iOS and Android",
      votes: 712,
      comments: 42,
      progress: 40,
    },
  ],
  planned: [
    {
      title: "Visual Agent Builder",
      description: "Drag-and-drop interface for creating custom agents",
      votes: 1089,
      comments: 67,
    },
    {
      title: "Data Warehouse Connectors",
      description: "Direct connections to Snowflake, BigQuery, Databricks",
      votes: 856,
      comments: 45,
    },
    {
      title: "Agent Marketplace",
      description: "Community-built agents and workflows",
      votes: 743,
      comments: 52,
    },
    {
      title: "Self-Hosted Option",
      description: "Deploy Gravitre in your own infrastructure",
      votes: 621,
      comments: 38,
    },
    {
      title: "Zapier/Make Integration",
      description: "Use Gravitre as a step in Zapier or Make workflows",
      votes: 534,
      comments: 29,
    },
  ],
  exploring: [
    {
      title: "Voice Commands",
      description: "Control Gravitre with voice through integrations",
      votes: 423,
      comments: 31,
    },
    {
      title: "Real-time Collaboration",
      description: "Multiple users editing workflows simultaneously",
      votes: 389,
      comments: 22,
    },
    {
      title: "AI-Powered Debugging",
      description: "AI assistant to help troubleshoot workflow issues",
      votes: 356,
      comments: 27,
    },
  ],
}

const StatusBadge = ({ status }: { status: string }) => {
  const styles = {
    shipped: "bg-emerald-100 text-emerald-700 border-emerald-200",
    inProgress: "bg-amber-100 text-amber-700 border-amber-200",
    planned: "bg-cyan-100 text-cyan-700 border-cyan-200",
    exploring: "bg-purple-100 text-purple-700 border-purple-200",
  }
  const labels = {
    shipped: "Shipped",
    inProgress: "In Progress",
    planned: "Planned",
    exploring: "Exploring",
  }
  return (
    <span className={`text-xs px-2 py-1 rounded border ${styles[status as keyof typeof styles]}`}>
      {labels[status as keyof typeof labels]}
    </span>
  )
}

export default function RoadmapPage() {
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
              Product Roadmap
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              See what we&apos;re building, vote on features you want, and help shape the future of Gravitre.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="#suggest"
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
              >
                Suggest a feature
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                href="/changelog"
                className="inline-flex items-center gap-2 text-sm text-emerald-600 hover:text-emerald-500"
              >
                View changelog
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Legend */}
      <section className="px-6 pb-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-wrap items-center justify-center gap-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span className="text-sm text-zinc-600">Shipped</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-600" />
              <span className="text-sm text-zinc-600">In Progress</span>
            </div>
            <div className="flex items-center gap-2">
              <Circle className="h-4 w-4 text-cyan-600" />
              <span className="text-sm text-zinc-600">Planned</span>
            </div>
            <div className="flex items-center gap-2">
              <Circle className="h-4 w-4 text-purple-600" />
              <span className="text-sm text-zinc-600">Exploring</span>
            </div>
          </div>
        </div>
      </section>

      {/* In Progress */}
      <section className="px-6 py-12 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center gap-3 mb-8"
          >
            <Clock className="h-5 w-5 text-amber-600" />
            <h2 className="text-xl font-semibold text-zinc-900">In Progress</h2>
          </motion.div>
          <div className="space-y-4">
            {roadmapItems.inProgress.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-medium text-zinc-900">{item.title}</h3>
                      <StatusBadge status="inProgress" />
                    </div>
                    <p className="text-sm text-zinc-600 mb-4">{item.description}</p>
                    {/* Progress bar */}
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-2 rounded-full bg-zinc-200">
                        <div 
                          className="h-2 rounded-full bg-amber-500 transition-all"
                          style={{ width: `${item.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500">{item.progress}%</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-zinc-500">
                    <span className="flex items-center gap-1">
                      <ThumbsUp className="h-3 w-3" />
                      {item.votes}
                    </span>
                    <span className="flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" />
                      {item.comments}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Planned */}
      <section className="px-6 py-12 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center gap-3 mb-8"
          >
            <Circle className="h-5 w-5 text-cyan-600" />
            <h2 className="text-xl font-semibold text-zinc-900">Planned</h2>
          </motion.div>
          <div className="space-y-3">
            {roadmapItems.planned.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
              >
                <div>
                  <h3 className="font-medium text-zinc-900">{item.title}</h3>
                  <p className="text-sm text-zinc-500 mt-0.5">{item.description}</p>
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-500 shrink-0">
                  <button className="flex items-center gap-1 hover:text-emerald-600 transition-colors">
                    <ThumbsUp className="h-3 w-3" />
                    {item.votes}
                  </button>
                  <span className="flex items-center gap-1">
                    <MessageSquare className="h-3 w-3" />
                    {item.comments}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Exploring */}
      <section className="px-6 py-12 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center gap-3 mb-8"
          >
            <Circle className="h-5 w-5 text-purple-600" />
            <h2 className="text-xl font-semibold text-zinc-900">Exploring</h2>
            <span className="text-xs text-zinc-500">Ideas we&apos;re considering</span>
          </motion.div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {roadmapItems.exploring.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
              >
                <h3 className="font-medium text-zinc-900 text-sm">{item.title}</h3>
                <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{item.description}</p>
                <div className="flex items-center gap-3 mt-3 text-xs text-zinc-500">
                  <button className="flex items-center gap-1 hover:text-emerald-600 transition-colors">
                    <ThumbsUp className="h-3 w-3" />
                    {item.votes}
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Recently Shipped */}
      <section className="px-6 py-12 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center gap-3 mb-8"
          >
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <h2 className="text-xl font-semibold text-zinc-900">Recently Shipped</h2>
          </motion.div>
          <div className="grid gap-3 sm:grid-cols-2">
            {roadmapItems.shipped.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <h3 className="font-medium text-zinc-900 text-sm">{item.title}</h3>
                </div>
                <p className="text-xs text-zinc-600 ml-6">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Suggest Feature */}
      <section id="suggest" className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Have an idea?</h2>
            <p className="text-zinc-600 mb-8">
              We&apos;d love to hear your feature requests and feedback.
            </p>
            <form className="space-y-4">
              <input
                type="email"
                placeholder="Your email"
                className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none"
              />
              <textarea
                placeholder="Describe your feature idea..."
                rows={4}
                className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none resize-none"
              />
              <button
                type="submit"
                className="w-full rounded-lg bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-500"
              >
                Submit suggestion
              </button>
            </form>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
