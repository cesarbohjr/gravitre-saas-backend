"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Sparkles, Wrench, Shield, Zap } from "lucide-react"

const releases = [
  { version: "2.4.0", date: "April 5, 2026", title: "Multi-Agent Collaboration", description: "Agents can now work together on complex tasks, passing context and sharing results in real-time.", type: "feature", highlights: ["Agent-to-agent communication protocol", "Shared memory between collaborating agents", "Visual collaboration graph in workflow builder", "Performance improvements for parallel execution"] },
  { version: "2.3.2", date: "March 28, 2026", title: "Security Enhancements", description: "Major security improvements with enhanced encryption, audit logging, and access controls for enterprise customers.", type: "security", highlights: ["Enhanced audit logging", "IP allowlisting for API access", "Session management improvements", "End-to-end encryption updates"] },
  { version: "2.3.0", date: "March 21, 2026", title: "Workflow Templates Library", description: "50+ pre-built workflow templates to help you get started faster.", type: "feature", highlights: ["Sales automation templates", "Marketing operations templates", "Finance and reporting templates", "One-click template deployment"] },
  { version: "2.2.5", date: "March 14, 2026", title: "Performance & Reliability", description: "Major performance improvements and bug fixes across the platform.", type: "improvement", highlights: ["50% faster workflow execution", "Improved error recovery", "Better handling of large datasets", "Fixed: Connector sync issues"] },
  { version: "2.2.0", date: "March 7, 2026", title: "Advanced Scheduling", description: "New scheduling options including cron expressions, time zones, and calendar-aware triggers.", type: "feature", highlights: ["Cron expression support", "Time zone-aware scheduling", "Business day calendars", "Holiday-aware triggers"] },
  { version: "2.1.3", date: "February 28, 2026", title: "API v2 & New SDKs", description: "Introducing API v2 with improved consistency and new official SDKs.", type: "feature", highlights: ["REST API v2 with OpenAPI spec", "Official Node.js SDK", "Official Python SDK", "Webhook signature verification"] },
  { version: "2.0.0", date: "February 1, 2026", title: "AI Operator 2.0", description: "Major release with multi-agent orchestration, improved reasoning, and 10x faster execution.", type: "major", highlights: ["Multi-agent orchestration", "Advanced reasoning engine", "10x faster task execution", "New conversation memory", "Enhanced error handling", "Redesigned dashboard"] },
]

const getTypeIcon = (type: string) => {
  switch (type) {
    case "feature": return <Sparkles className="h-4 w-4" />
    case "improvement": return <Zap className="h-4 w-4" />
    case "security": return <Shield className="h-4 w-4" />
    case "major": return <Sparkles className="h-4 w-4" />
    default: return <Wrench className="h-4 w-4" />
  }
}

const getTypeColor = (type: string) => {
  switch (type) {
    case "feature": return "bg-emerald-100 text-emerald-700 border-emerald-200"
    case "improvement": return "bg-cyan-100 text-cyan-700 border-cyan-200"
    case "security": return "bg-amber-100 text-amber-700 border-amber-200"
    case "major": return "bg-purple-100 text-purple-700 border-purple-200"
    default: return "bg-zinc-100 text-zinc-600 border-zinc-200"
  }
}

export default function ChangelogPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">Changelog</h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">New features, improvements, and fixes. Stay up to date with everything we&apos;re building.</p>
            <div className="mt-8">
              <Link href="/roadmap" className="inline-flex items-center gap-2 text-sm text-emerald-600 hover:text-emerald-500">View our roadmap<ArrowRight className="h-4 w-4" /></Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Subscribe */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-2xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="rounded-xl border border-zinc-200 bg-white p-6 text-center shadow-sm">
            <p className="text-sm text-zinc-600 mb-4">Get notified when we ship new features</p>
            <form className="flex gap-3 max-w-md mx-auto">
              <input type="email" placeholder="Enter your email" className="flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500" />
              <button type="submit" className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-all hover:bg-emerald-500">Subscribe</button>
            </form>
          </motion.div>
        </div>
      </section>

      {/* Timeline */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-3xl">
          <div className="relative">
            <div className="absolute left-0 md:left-24 top-0 bottom-0 w-px bg-zinc-200" />
            <div className="space-y-12">
              {releases.map((release, i) => (
                <motion.div key={release.version} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="relative pl-8 md:pl-36">
                  <div className="absolute left-0 md:left-24 top-0 -translate-x-1/2">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${getTypeColor(release.type)}`}>{getTypeIcon(release.type)}</div>
                  </div>
                  <div className="absolute left-0 top-1 hidden md:block w-20 text-right">
                    <span className="text-xs text-zinc-500">{release.date}</span>
                  </div>
                  <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <span className="text-xs font-mono text-emerald-700 bg-emerald-100 px-2 py-1 rounded">v{release.version}</span>
                      <span className={`text-xs px-2 py-1 rounded border ${getTypeColor(release.type)}`}>{release.type.charAt(0).toUpperCase() + release.type.slice(1)}</span>
                      <span className="text-xs text-zinc-500 md:hidden">{release.date}</span>
                    </div>
                    <h3 className="text-lg font-medium text-zinc-900 mb-2">{release.title}</h3>
                    <p className="text-sm text-zinc-600 mb-4">{release.description}</p>
                    <ul className="space-y-2">
                      {release.highlights.map((highlight) => (
                        <li key={highlight} className="flex items-start gap-2 text-sm text-zinc-500"><span className="text-emerald-600 mt-1">-</span>{highlight}</li>
                      ))}
                    </ul>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="mt-12 text-center">
            <button className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">View older releases<ArrowRight className="h-4 w-4" /></button>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Have feature requests?</h2>
            <p className="text-zinc-600 mb-8">We&apos;d love to hear from you. Share your ideas and vote on features in our public roadmap.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/roadmap" className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800">View roadmap<ArrowRight className="h-4 w-4" /></Link>
              <Link href="/contact" className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">Send feedback</Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
