"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Sparkles, Wrench, Shield, Zap } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const releases = [
  ...MARKETING_COPY.changelog.releases,
  { version: "2.4.0", date: "April 5, 2026", title: "Multi-Agent Collaboration", description: "Coordinate multiple agents on complex tasks with defined roles. Each sub-agent completes its scoped work; results are aggregated after completion—not live shared memory.", type: "feature", highlights: ["Parallel sub-agent jobs via the agent queue", "Council-style aggregation of completed subtask results", "Collaboration graph in workflow builder", "Parallel job scheduling improvements"] },
  { version: "2.3.2", date: "March 28, 2026", title: "Security Enhancements", description: "Major security improvements with enhanced encryption, audit logging, and access controls for enterprise customers.", type: "security", highlights: ["Enhanced audit logging", "IP allowlisting for API access", "Session management improvements", "End-to-end encryption updates"] },
  { version: "2.3.0", date: "March 21, 2026", title: "Workflow Templates Library", description: "50+ pre-built workflow templates to help you get started faster.", type: "feature", highlights: ["Sales automation templates", "Marketing operations templates", "Finance and reporting templates", "One-click template deployment"] },
  { version: "2.2.5", date: "March 14, 2026", title: "Performance & Reliability", description: "Major performance improvements and bug fixes across the platform.", type: "improvement", highlights: ["50% faster workflow execution", "Improved error recovery", "Better handling of large datasets", "Fixed: Connector sync issues"] },
  { version: "2.2.0", date: "March 7, 2026", title: "Advanced Scheduling", description: "New scheduling options including cron expressions, time zones, and calendar-aware triggers.", type: "feature", highlights: ["Cron expression support", "Time zone-aware scheduling", "Business day calendars", "Holiday-aware triggers"] },
  { version: "2.1.3", date: "February 28, 2026", title: "API v2 & New SDKs", description: "Introducing API v2 with improved consistency and new official SDKs.", type: "feature", highlights: ["REST API v2 with OpenAPI spec", "Official Node.js SDK", "Official Python SDK", "Webhook signature verification"] },
  { version: "2.0.0", date: "February 1, 2026", title: "AI Operator 2.0", description: "Major release with durable async operator analysis, ReAct-style reasoning when integrations are connected, and structured task outputs.", type: "major", highlights: ["Async operator analysis jobs", "ReAct-style reasoning on connected integrations", "Structured plans, findings, and recommended actions", "Conversation memory improvements", "Enhanced error handling", "Redesigned dashboard"] },
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
    // "major" is the marquee release — strongest emerald emphasis.
    case "major": return "bg-primary text-white border-emerald-600"
    case "feature": return "bg-primary/15 text-primary border-primary/20"
    // Neutral zinc keeps "improvement" distinct without adding an off-brand hue.
    case "improvement": return "bg-muted text-foreground border-border"
    // Amber is reserved for security/attention items.
    case "security": return "bg-amber-100 text-amber-700 border-amber-200"
    default: return "bg-muted text-muted-foreground border-border"
  }
}

export default function ChangelogPage() {
  return (
    <div className="bg-card">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">Changelog</h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">{MARKETING_COPY.changelog.subtitle}</p>
            <div className="mt-8">
              <Link href="/roadmap" className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary">View our roadmap<ArrowRight className="h-4 w-4" /></Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Subscribe */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-2xl">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="rounded-xl border border-border bg-card p-6 text-center shadow-sm">
            <p className="text-sm text-muted-foreground mb-4">Get notified when we ship new features</p>
            <form className="flex gap-3 max-w-md mx-auto">
              <input type="email" placeholder="Enter your email" className="flex-1 rounded-lg border border-border bg-card px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" />
              <button type="submit" className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary/100">Subscribe</button>
            </form>
          </motion.div>
        </div>
      </section>

      {/* Timeline */}
      <section className="px-6 py-16 border-t border-border">
        <div className="mx-auto max-w-3xl">
          <div className="relative">
            <div className="absolute left-0 md:left-24 top-0 bottom-0 w-px bg-muted" />
            <div className="space-y-12">
              {releases.map((release, i) => (
                <motion.div key={release.version} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="relative pl-8 md:pl-36">
                  <div className="absolute left-0 md:left-24 top-0 -translate-x-1/2">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${getTypeColor(release.type)}`}>{getTypeIcon(release.type)}</div>
                  </div>
                  <div className="absolute left-0 top-1 hidden md:block w-20 text-right">
                    <span className="text-xs text-muted-foreground">{release.date}</span>
                  </div>
                  <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <span className="text-xs font-mono text-primary bg-primary/15 px-2 py-1 rounded">v{release.version}</span>
                      <span className={`text-xs px-2 py-1 rounded border ${getTypeColor(release.type)}`}>{release.type.charAt(0).toUpperCase() + release.type.slice(1)}</span>
                      <span className="text-xs text-muted-foreground md:hidden">{release.date}</span>
                    </div>
                    <h3 className="text-lg font-medium text-foreground mb-2">{release.title}</h3>
                    <p className="text-sm text-muted-foreground mb-4">{release.description}</p>
                    <ul className="space-y-2">
                      {release.highlights.map((highlight) => (
                        <li key={highlight} className="flex items-start gap-2 text-sm text-muted-foreground"><span className="text-primary mt-1">-</span>{highlight}</li>
                      ))}
                    </ul>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="mt-12 text-center">
            <button className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted">View older releases<ArrowRight className="h-4 w-4" /></button>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-24 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h2 className="text-2xl font-semibold text-foreground mb-4">Have feature requests?</h2>
            <p className="text-muted-foreground mb-8">We&apos;d love to hear from you. Share your ideas and vote on features in our public roadmap.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/roadmap" className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90">View roadmap<ArrowRight className="h-4 w-4" /></Link>
              <Link href="/contact" className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted">Send feedback</Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
