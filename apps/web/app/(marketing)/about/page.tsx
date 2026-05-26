"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Linkedin, Twitter, Zap, Shield, Users, Globe, ChevronRight, Sparkles } from "lucide-react"

const founder = {
  name: "Cesar Bohorquez Jr",
  role: "Founder & CEO",
  bio: "Serial entrepreneur and technologist with a passion for building products that empower businesses through intelligent automation. Previously founded and scaled multiple technology ventures. Now focused on democratizing AI operations for enterprises of all sizes.",
  image: "/images/team/cesar-bohorquez.jpg",
  linkedin: "https://www.linkedin.com/in/cesarbohorquezjr/",
  twitter: "https://twitter.com/cesarbohorquezjr",
  imageStyle: { objectPosition: "center 15%" },
}

const values = [
  {
    icon: Zap,
    title: "Move fast with intention",
    description: "We ship quickly but never compromise on quality. Every feature is designed with purpose and precision.",
  },
  {
    icon: Shield,
    title: "Trust through transparency",
    description: "AI should be explainable. We build tools that show their work and earn user confidence at every step.",
  },
  {
    icon: Users,
    title: "Empower, don't replace",
    description: "Our AI augments human capability. We believe in collaboration between humans and machines.",
  },
  {
    icon: Globe,
    title: "Enterprise-grade, startup-fast",
    description: "Security and compliance at scale, with the agility and innovation speed of a startup.",
  },
]

const capabilities = [
  { label: "Workflow Automation", description: "Intelligent task orchestration" },
  { label: "AI Agents", description: "Autonomous decision-making" },
  { label: "Data Sync", description: "Real-time integrations" },
  { label: "Analytics", description: "Actionable insights" },
]

const timeline = [
  { 
    year: "2024", 
    title: "The Beginning",
    event: "Founded by Cesar Bohorquez Jr with a clear vision: make enterprise AI accessible to every organization.",
    highlight: true,
  },
  { 
    year: "2025", 
    title: "Private Beta",
    event: "Launched the Gravitre AI Operator platform to select enterprise partners for intensive development feedback.",
  },
  { 
    year: "2026", 
    title: "Public Launch",
    event: "Opening access to businesses of all sizes, democratizing AI-powered operations globally.",
    current: true,
  },
]

export default function AboutPage() {
  return (
    <div className="bg-zinc-950 text-white">
      {/* Hero - Dark with gradient accent */}
      <section className="relative overflow-hidden px-6 py-32 lg:py-48">
        {/* Gradient orb */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-to-br from-emerald-500/30 via-teal-500/20 to-transparent rounded-full blur-3xl" />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
        
        <div className="relative mx-auto max-w-5xl">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-center mb-8"
          >
            <span className="inline-flex items-center gap-2 rounded-full bg-white/5 backdrop-blur-sm px-4 py-2 text-sm font-medium text-emerald-400 ring-1 ring-white/10">
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
              <span className="text-white">We&apos;re building </span>
              <br className="hidden sm:block" />
              <span className="bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400 bg-clip-text text-transparent">
                the AI command center
              </span>
              <br className="hidden sm:block" />
              <span className="text-white">for operations teams</span>
            </h1>
          </motion.div>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-8 text-lg sm:text-xl text-zinc-400 max-w-3xl mx-auto text-center leading-relaxed"
          >
            Gravitre empowers organizations to automate complex workflows, deploy intelligent agents, 
            and transform how work gets done. Our mission is simple: let AI handle the repetitive 
            so your team can focus on what matters.
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
              className="group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-zinc-900 transition-all hover:bg-zinc-100"
            >
              Get started free
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-white/5 px-6 py-3.5 text-sm font-semibold text-white ring-1 ring-white/10 transition-all hover:bg-white/10"
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
                className="relative group rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 p-6 transition-all hover:bg-white/10 hover:border-emerald-500/30"
              >
                <div className="text-lg font-semibold text-white mb-1">{cap.label}</div>
                <div className="text-sm text-zinc-500">{cap.description}</div>
                <ChevronRight className="absolute top-6 right-6 h-4 w-4 text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity" />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Mission - Split layout */}
      <section className="relative px-6 py-32 bg-zinc-900/50">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-16 lg:grid-cols-2 lg:gap-24 items-center">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <span className="text-emerald-400 text-sm font-semibold uppercase tracking-wider">Our Mission</span>
              <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-white leading-tight">
                Eliminating the busywork that holds teams back
              </h2>
              <div className="mt-8 space-y-6 text-zinc-400 text-lg leading-relaxed">
                <p>
                  Every day, millions of hours are lost to repetitive, manual tasks that drain teams and slow down businesses. 
                  We founded Gravitre to change that reality.
                </p>
                <p>
                  Our platform enables businesses to deploy AI agents that work alongside human teams, handling everything from 
                  data synchronization to complex multi-step workflows with complete transparency.
                </p>
                <p className="text-white font-medium">
                  We believe AI should be a force multiplier for human creativity, not a black box.
                </p>
              </div>
              <div className="mt-10">
                <Link
                  href="/platform"
                  className="group inline-flex items-center gap-2 text-emerald-400 font-semibold hover:text-emerald-300 transition-colors"
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
                <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/20 to-teal-500/20 rounded-3xl blur-2xl" />
                <div className="relative rounded-3xl bg-zinc-800/50 border border-white/10 p-8 backdrop-blur-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                      <Zap className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="text-white font-semibold">AI-First Architecture</div>
                      <div className="text-sm text-zinc-500">Built for the future of work</div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    {[
                      { label: "Automation Coverage", value: "95%", color: "bg-emerald-500" },
                      { label: "Time Saved Per Task", value: "80%", color: "bg-teal-500" },
                      { label: "Enterprise Ready", value: "100%", color: "bg-cyan-500" },
                    ].map((metric) => (
                      <div key={metric.label}>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-zinc-400">{metric.label}</span>
                          <span className="text-white font-medium">{metric.value}</span>
                        </div>
                        <div className="h-2 rounded-full bg-zinc-700 overflow-hidden">
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
            <span className="text-emerald-400 text-sm font-semibold uppercase tracking-wider">Our Values</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-white">
              Principles that guide us
            </h2>
            <p className="mt-4 text-zinc-400 max-w-2xl mx-auto text-lg">
              These aren&apos;t just words on a wall. They shape every decision we make, every feature we build, 
              and every interaction with our customers.
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
                className="group relative rounded-3xl bg-zinc-900 border border-white/5 p-8 transition-all hover:border-emerald-500/30 overflow-hidden"
              >
                {/* Gradient hover effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                
                <div className="relative">
                  <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/20 flex items-center justify-center mb-6">
                    <value.icon className="h-6 w-6 text-emerald-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-3">{value.title}</h3>
                  <p className="text-zinc-400 leading-relaxed">{value.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Timeline - Horizontal on desktop */}
      <section className="px-6 py-32 bg-zinc-900/50">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="text-emerald-400 text-sm font-semibold uppercase tracking-wider">Our Journey</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-white">
              From vision to reality
            </h2>
          </motion.div>
          
          <div className="relative">
            {/* Timeline line */}
            <div className="hidden lg:block absolute top-12 left-0 right-0 h-px bg-gradient-to-r from-transparent via-zinc-700 to-transparent" />
            
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
                  <div className="hidden lg:flex absolute -top-0.5 left-1/2 -translate-x-1/2 h-6 w-6 rounded-full bg-zinc-900 border-2 border-zinc-700 items-center justify-center">
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
                  
                  <div className={`lg:mt-12 p-6 rounded-2xl ${item.current ? 'bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border border-emerald-500/20' : 'bg-zinc-800/50 border border-white/5'}`}>
                    <div className={`text-sm font-semibold mb-2 ${item.current ? 'text-emerald-400' : 'text-zinc-500'}`}>
                      {item.year}
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                    <p className="text-zinc-400 text-sm leading-relaxed">{item.event}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Founder - Large format */}
      <section className="px-6 py-32">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="text-emerald-400 text-sm font-semibold uppercase tracking-wider">Leadership</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-white">
              Meet the founder
            </h2>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-cyan-500/10 rounded-3xl blur-2xl" />
            <div className="relative rounded-3xl bg-zinc-900 border border-white/10 overflow-hidden">
              <div className="grid md:grid-cols-5">
                {/* Image */}
                <div className="md:col-span-2 relative">
                  <div className="aspect-square md:aspect-auto md:h-full">
                    <img
                      src={founder.image}
                      alt={founder.name}
                      className="h-full w-full object-cover"
                      style={founder.imageStyle}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t md:bg-gradient-to-r from-zinc-900 via-zinc-900/50 to-transparent" />
                  </div>
                </div>
                
                {/* Content */}
                <div className="md:col-span-3 p-8 md:p-12 flex flex-col justify-center">
                  <div className="text-emerald-400 text-sm font-semibold mb-2">{founder.role}</div>
                  <h3 className="text-3xl sm:text-4xl font-bold text-white mb-6">{founder.name}</h3>
                  <p className="text-zinc-400 text-lg leading-relaxed mb-8">
                    {founder.bio}
                  </p>
                  <div className="flex items-center gap-4">
                    <a 
                      href={founder.twitter} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-zinc-400 hover:text-white hover:border-white/20 transition-all"
                    >
                      <Twitter className="h-4 w-4" />
                      Twitter
                    </a>
                    <a 
                      href={founder.linkedin} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-zinc-400 hover:text-white hover:border-white/20 transition-all"
                    >
                      <Linkedin className="h-4 w-4" />
                      LinkedIn
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Join the Team - Prominent CTA */}
      <section className="px-6 py-32 bg-zinc-900/50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative text-center"
          >
            <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-cyan-500/20 rounded-3xl blur-3xl" />
            <div className="relative rounded-3xl bg-gradient-to-br from-zinc-800 to-zinc-900 border border-white/10 p-12 md:p-16">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-400 ring-1 ring-emerald-500/20 mb-6">
                <Users className="h-4 w-4" />
                Now hiring
              </div>
              <h3 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                Help us build the future
              </h3>
              <p className="text-zinc-400 max-w-xl mx-auto mb-8 text-lg">
                We&apos;re looking for exceptional engineers, designers, and operators who want to 
                shape the future of AI-powered automation. Remote-first, mission-driven.
              </p>
              <Link
                href="/careers"
                className="group inline-flex items-center gap-2 rounded-full bg-white px-8 py-4 text-base font-semibold text-zinc-900 transition-all hover:bg-zinc-100"
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
            <h2 className="text-4xl sm:text-5xl font-bold text-white mb-6">
              Ready to transform your operations?
            </h2>
            <p className="text-zinc-400 mb-10 max-w-2xl mx-auto text-lg">
              Join forward-thinking teams using Gravitre to automate workflows, 
              deploy AI agents, and focus on what truly matters.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 px-8 py-4 text-base font-semibold text-white transition-all hover:from-emerald-600 hover:to-teal-600"
              >
                Start free trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/demo"
                className="inline-flex items-center gap-2 rounded-full bg-white/5 px-8 py-4 text-base font-semibold text-white ring-1 ring-white/10 transition-all hover:bg-white/10"
              >
                Request a demo
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
