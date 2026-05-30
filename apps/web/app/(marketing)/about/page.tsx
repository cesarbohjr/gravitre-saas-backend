"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Zap, Shield, Users, Globe, ChevronRight, Sparkles } from "lucide-react"

const values = [
  {
    icon: Zap,
    title: "Strategy over busywork",
    description: "Your team was hired for their judgment, creativity, and expertise. We build AI that handles the repetitive so they can focus on what actually moves the needle.",
  },
  {
    icon: Shield,
    title: "Transparency builds trust",
    description: "Black-box AI creates anxiety. Every Gravitre agent shows its reasoning, explains its decisions, and keeps humans in control of what matters.",
  },
  {
    icon: Users,
    title: "Amplify, never replace",
    description: "The best work happens when humans and AI collaborate. We give your team superpowers, not pink slips.",
  },
  {
    icon: Globe,
    title: "Enterprise-ready, human-centered",
    description: "Security and compliance are table stakes. We go further by designing AI that people actually want to work with.",
  },
]

const capabilities = [
  { label: "Intelligent Delegation", description: "Hand off the mundane" },
  { label: "Strategic Focus", description: "More thinking, less clicking" },
  { label: "Seamless Handoffs", description: "AI and human, in sync" },
  { label: "Decision Support", description: "Insights when you need them" },
]

const timeline = [
  { 
    year: "2024", 
    title: "The Beginning",
    event: "We watched brilliant people spend 60% of their day on tasks a machine should handle. Gravitre was born to fix that.",
    highlight: true,
  },
  { 
    year: "2025", 
    title: "Private Beta",
    event: "Partnered with forward-thinking operations teams to build AI agents that actually fit how people work.",
  },
  { 
    year: "2026", 
    title: "Public Launch",
    event: "Now helping teams everywhere reclaim their time for the strategic, creative work they were hired to do.",
    current: true,
  },
]

export default function AboutPage() {
  return (
    <div className="bg-white text-zinc-900">
      {/* Hero - Light with gradient accent */}
      <section className="relative overflow-hidden px-6 py-32 lg:py-48">
        {/* Gradient orb */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-br from-emerald-200/60 via-teal-100/40 to-transparent rounded-full blur-3xl" />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />
        
        <div className="relative mx-auto max-w-5xl">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-center mb-8"
          >
            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 ring-1 ring-emerald-200">
              <Sparkles className="h-4 w-4" />
              Our Story
            </span>
          </motion.div>
          
          {/* Main headline */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.6 }}
            className="text-center"
          >
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1]">
              <span className="text-zinc-900">We help workers be </span>
              <br className="hidden sm:block" />
              <span className="bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 bg-clip-text text-transparent">
                more strategic
              </span>
              <br className="hidden sm:block" />
              <span className="text-zinc-900">and less robotic</span>
            </h1>
          </motion.div>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-8 text-lg sm:text-xl text-zinc-600 max-w-3xl mx-auto text-center leading-relaxed"
          >
            Your team didn&apos;t spend years building expertise just to copy-paste data between systems.
            Gravitre deploys AI agents that handle the mechanical work, so your people can do the 
            thinking, deciding, and creating that actually matters.
          </motion.p>
          
          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link
              href="/get-started"
              className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3.5 text-sm font-semibold text-white transition-all hover:bg-zinc-800"
            >
              Get started free
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-zinc-100 px-6 py-3.5 text-sm font-semibold text-zinc-900 transition-all hover:bg-zinc-200"
            >
              Contact sales
            </Link>
          </motion.div>
          
          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="mt-20 grid grid-cols-2 lg:grid-cols-4 gap-4"
          >
            {capabilities.map((cap, i) => (
              <motion.div
                key={cap.label}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.6 + i * 0.1 }}
                className="relative group rounded-2xl bg-zinc-50 border border-zinc-200 p-6 transition-all hover:bg-white hover:border-emerald-300 hover:shadow-lg"
              >
                <div className="text-lg font-semibold text-zinc-900 mb-1">{cap.label}</div>
                <div className="text-sm text-zinc-500">{cap.description}</div>
                <ChevronRight className="absolute top-6 right-6 h-4 w-4 text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Mission - Split layout */}
      <section className="relative px-6 py-32 bg-zinc-50">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-16 lg:grid-cols-2 lg:gap-24 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <span className="text-emerald-600 text-sm font-semibold uppercase tracking-wider">Our Mission</span>
              <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-zinc-900 leading-tight">
                The best people deserve better than busywork
              </h2>
              <div className="mt-8 space-y-6 text-zinc-600 text-lg leading-relaxed">
                <p>
                  Operations professionals are problem-solvers, negotiators, and strategic thinkers. 
                  Yet most spend their days on tasks that don&apos;t require any of those skills: updating 
                  spreadsheets, chasing approvals, copying data from one system to another.
                </p>
                <p>
                  We built Gravitre because we believe that&apos;s a waste of human potential. Our AI agents 
                  take on the robotic work, the stuff that follows rules and patterns, so your team 
                  can focus on the judgment calls, relationship building, and creative problem-solving 
                  that machines simply can&apos;t do.
                </p>
                <p className="text-zinc-900 font-medium">
                  When AI handles the mechanical, humans get to be human again.
                </p>
              </div>
              <div className="mt-10">
                <Link
                  href="/platform"
                  className="group inline-flex items-center gap-2 text-emerald-600 font-semibold hover:text-emerald-700 transition-colors"
                >
                  Explore our platform
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="relative"
            >
              {/* Decorative card stack */}
              <div className="relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-emerald-100/80 to-teal-100/80 rounded-3xl blur-2xl" />
                <div className="relative rounded-3xl bg-white border border-zinc-200 p-8 shadow-xl">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                      <Zap className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="text-zinc-900 font-semibold">Human-Centered AI</div>
                      <div className="text-sm text-zinc-500">Built to elevate, not eliminate</div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    {[
                      { label: "Time Freed for Strategy", value: "70%", color: "bg-emerald-500" },
                      { label: "Manual Tasks Delegated", value: "85%", color: "bg-teal-500" },
                      { label: "Team Satisfaction", value: "94%", color: "bg-cyan-500" },
                    ].map((metric) => (
                      <div key={metric.label}>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-zinc-500">{metric.label}</span>
                          <span className="text-zinc-900 font-medium">{metric.value}</span>
                        </div>
                        <div className="h-2 rounded-full bg-zinc-100 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            whileInView={{ width: metric.value }}
                            viewport={{ once: true }}
                            transition={{ duration: 1, delay: 0.3 }}
                            className={`h-full rounded-full ${metric.color}`}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Values - Full width cards */}
      <section className="px-6 py-32">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="text-emerald-600 text-sm font-semibold uppercase tracking-wider">Our Values</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-zinc-900">
              What we believe
            </h2>
            <p className="mt-4 text-zinc-600 max-w-2xl mx-auto text-lg">
              We&apos;re building AI for people who are tired of feeling like robots. 
              These principles guide every decision we make.
            </p>
          </motion.div>
          
          <div className="grid gap-6 md:grid-cols-2">
            {values.map((value, i) => (
              <motion.div
                key={value.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group relative rounded-3xl bg-zinc-50 border border-zinc-200 p-8 transition-all hover:bg-white hover:border-emerald-300 hover:shadow-lg overflow-hidden"
              >
                {/* Gradient hover effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                
                <div className="relative">
                  <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 border border-emerald-200 flex items-center justify-center mb-6">
                    <value.icon className="h-6 w-6 text-emerald-600" />
                  </div>
                  <h3 className="text-xl font-semibold text-zinc-900 mb-3">{value.title}</h3>
                  <p className="text-zinc-600 leading-relaxed">{value.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Timeline - Horizontal on desktop */}
      <section className="px-6 py-32 bg-zinc-50">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="text-emerald-600 text-sm font-semibold uppercase tracking-wider">Our Journey</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-zinc-900">
              Built by people who get it
            </h2>
          </motion.div>
          
          <div className="relative">
            {/* Timeline line */}
            <div className="hidden lg:block absolute top-12 left-0 right-0 h-px bg-gradient-to-r from-transparent via-zinc-300 to-transparent" />
            
            <div className="grid gap-8 lg:grid-cols-3">
              {timeline.map((item, i) => (
                <motion.div
                  key={item.year}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.15 }}
                  className="relative"
                >
                  {/* Timeline dot */}
                  <div className="hidden lg:flex absolute -top-0.5 left-1/2 -translate-x-1/2 h-6 w-6 rounded-full bg-white border-2 border-zinc-300 items-center justify-center shadow-sm">
                    {item.current && (
                      <motion.div 
                        className="h-2 w-2 rounded-full bg-emerald-500"
                        animate={{ scale: [1, 1.5, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    )}
                    {item.highlight && (
                      <div className="h-2 w-2 rounded-full bg-emerald-500" />
                    )}
                  </div>
                  
                  <div className={`lg:mt-12 p-6 rounded-2xl ${item.current ? 'bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 shadow-md' : 'bg-white border border-zinc-200'}`}>
                    <div className={`text-sm font-semibold mb-2 ${item.current ? 'text-emerald-600' : 'text-zinc-400'}`}>
                      {item.year}
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-900 mb-2">{item.title}</h3>
                    <p className="text-zinc-600 text-sm leading-relaxed">{item.event}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Join the Team - Prominent CTA */}
      <section className="px-6 py-32 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="absolute -inset-4 bg-gradient-to-r from-emerald-200/50 to-teal-200/50 rounded-3xl blur-2xl" />
            <div className="relative rounded-3xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 p-12 text-center">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2 text-sm font-medium text-emerald-700 mb-6">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                </span>
                Now hiring
              </div>
              <h3 className="text-3xl sm:text-4xl font-bold text-zinc-900 mb-4">
                Join the mission
              </h3>
              <p className="text-zinc-600 max-w-xl mx-auto mb-8 text-lg">
                We&apos;re looking for people who believe work should be meaningful. Engineers, designers, 
                and operators who want to help teams everywhere spend less time on busywork and more time 
                on the work that matters.
              </p>
              <Link
                href="/careers"
                className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-sm font-semibold text-white transition-all hover:bg-zinc-800"
              >
                View open positions
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-6 py-32">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl sm:text-5xl font-bold text-zinc-900 mb-6">
              Ready to reclaim your team&apos;s time?
            </h2>
            <p className="text-zinc-600 text-lg mb-10 max-w-xl mx-auto">
              See how Gravitre helps operations teams stop acting like robots and start 
              doing the strategic work they were hired for.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-emerald-600 to-teal-600 px-8 py-4 text-sm font-semibold text-white transition-all hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-500/25"
              >
                Start free trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-8 py-4 text-sm font-semibold text-zinc-700 transition-all hover:bg-zinc-100"
              >
                Contact us
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
