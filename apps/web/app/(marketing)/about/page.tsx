"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, ArrowUpRight } from "lucide-react"

const stats = [
  { value: "70%", label: "Time freed for strategy" },
  { value: "10x", label: "Faster workflows" },
  { value: "94%", label: "Team satisfaction" },
]

const principles = [
  {
    number: "01",
    title: "Strategy over busywork",
    description: "AI handles the repetitive. Humans do the thinking.",
  },
  {
    number: "02", 
    title: "Amplify, never replace",
    description: "We give your team superpowers, not pink slips.",
  },
  {
    number: "03",
    title: "Transparency builds trust",
    description: "Every agent shows its reasoning. No black boxes.",
  },
]

const milestones = [
  { year: "2024", text: "Founded to fix how work gets done" },
  { year: "2025", text: "Private beta with enterprise partners" },
  { year: "2026", text: "Public launch", current: true },
]

export default function AboutPage() {
  return (
    <div className="bg-white">
      {/* Hero - Bold statement */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        {/* Subtle gradient background */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-50 via-white to-white" />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.015)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.015)_1px,transparent_1px)] bg-[size:72px_72px]" />
        
        <div className="relative px-6 py-32 max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1 className="text-[clamp(2.5rem,8vw,6rem)] font-bold tracking-tight leading-[0.95] text-zinc-900">
              Humans should
              <br />
              <span className="bg-gradient-to-r from-emerald-600 via-teal-500 to-emerald-600 bg-clip-text text-transparent bg-[length:200%_auto] animate-gradient">
                think
              </span>
              <br />
              not click
            </h1>
          </motion.div>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="mt-8 text-xl sm:text-2xl text-zinc-500 max-w-2xl mx-auto font-light"
          >
            We build AI agents that handle the mechanical work,
            so your team can do what they were actually hired for.
          </motion.p>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mt-12 flex items-center justify-center gap-6"
          >
            <Link
              href="/get-started"
              className="group inline-flex items-center gap-2 bg-zinc-900 text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-zinc-800 hover:scale-[1.02]"
            >
              Get started
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
            </Link>
            <Link
              href="/features"
              className="group inline-flex items-center gap-2 text-zinc-600 hover:text-zinc-900 text-sm font-medium transition-colors"
            >
              See how it works
              <ArrowUpRight className="h-4 w-4" strokeWidth={1.5} />
            </Link>
          </motion.div>
        </div>
        
        {/* Scroll indicator */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="absolute bottom-12 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
            className="w-px h-16 bg-gradient-to-b from-zinc-300 to-transparent"
          />
        </motion.div>
      </section>

      {/* Stats - Clean horizontal layout */}
      <section className="border-y border-zinc-100">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-zinc-100">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="py-16 md:px-12 first:md:pl-0 last:md:pr-0 text-center md:text-left"
              >
                <div className="text-5xl sm:text-6xl font-bold text-zinc-900 tracking-tight">
                  {stat.value}
                </div>
                <div className="mt-2 text-zinc-500 text-sm uppercase tracking-wider">
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Mission - Large text block */}
      <section className="py-32 lg:py-48 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <span className="text-emerald-600 text-sm font-medium uppercase tracking-wider">Our belief</span>
            <h2 className="mt-6 text-3xl sm:text-4xl lg:text-5xl font-medium text-zinc-900 leading-[1.2]">
              Operations professionals are problem-solvers, negotiators, and strategic thinkers. 
              <span className="text-zinc-400"> Yet most spend their days updating spreadsheets and chasing approvals.</span>
            </h2>
            <p className="mt-8 text-xl text-zinc-500 leading-relaxed">
              We built Gravitre because that&apos;s a waste of human potential. When AI handles the mechanical, 
              humans get to be human again.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Principles - Numbered list */}
      <section className="py-32 px-6 bg-zinc-50">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-20"
          >
            <span className="text-emerald-600 text-sm font-medium uppercase tracking-wider">How we think</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">Our principles</h2>
          </motion.div>
          
          <div className="space-y-0">
            {principles.map((principle, i) => (
              <motion.div
                key={principle.number}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group border-t border-zinc-200 py-12 flex flex-col md:flex-row md:items-center gap-6 md:gap-16"
              >
                <span className="text-emerald-600 text-sm font-mono">{principle.number}</span>
                <h3 className="text-2xl sm:text-3xl font-semibold text-zinc-900 flex-1 group-hover:text-emerald-600 transition-colors">
                  {principle.title}
                </h3>
                <p className="text-zinc-500 md:text-right md:max-w-xs">
                  {principle.description}
                </p>
              </motion.div>
            ))}
            <div className="border-t border-zinc-200" />
          </div>
        </div>
      </section>

      {/* Timeline - Minimal */}
      <section className="py-32 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16"
          >
            <span className="text-emerald-600 text-sm font-medium uppercase tracking-wider">Our journey</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-zinc-900 tracking-tight">Built fast, built right</h2>
          </motion.div>
          
          <div className="space-y-8">
            {milestones.map((milestone, i) => (
              <motion.div
                key={milestone.year}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-center gap-8"
              >
                <span className={`text-sm font-mono w-16 ${milestone.current ? 'text-emerald-600' : 'text-zinc-400'}`}>
                  {milestone.year}
                </span>
                <div className="flex items-center gap-4 flex-1">
                  <div className={`h-2 w-2 rounded-full ${milestone.current ? 'bg-emerald-500' : 'bg-zinc-300'}`} />
                  <span className={`text-lg ${milestone.current ? 'text-zinc-900 font-medium' : 'text-zinc-500'}`}>
                    {milestone.text}
                  </span>
                  {milestone.current && (
                    <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
                      Now
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Careers CTA */}
      <section className="py-32 px-6 bg-zinc-50">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="inline-flex items-center gap-2 text-sm text-emerald-600 font-medium mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600" />
              </span>
              We&apos;re hiring
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold text-zinc-900 tracking-tight">
              Join the mission
            </h2>
            <p className="mt-6 text-xl text-zinc-500 max-w-xl mx-auto">
              Help us give every team their time back.
            </p>
            <Link
              href="/careers"
              className="mt-10 group inline-flex items-center gap-2 bg-zinc-900 text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-zinc-800"
            >
              View open roles
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Final CTA - Full bleed */}
      <section className="relative py-32 lg:py-48 px-6 bg-gradient-to-b from-white to-emerald-50 overflow-hidden">
        {/* Gradient accent */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-gradient-to-b from-emerald-100/50 to-transparent rounded-full blur-3xl" />
        
        <div className="relative max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-zinc-900 tracking-tight leading-[1.1]">
              Ready to reclaim
              <br />
              your team&apos;s time?
            </h2>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 bg-zinc-900 text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-zinc-800"
              >
                Start free trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-900 px-8 py-4 text-sm font-medium transition-colors"
              >
                Contact sales
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
