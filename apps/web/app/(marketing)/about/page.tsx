"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const stats = [
  { value: "4-layer", label: "Intelligence stack" },
  { value: "Verified", label: "Learning signals only" },
  { value: "Live", label: "Connector executability" },
]

const principles = MARKETING_COPY.about.principles.map((item, index) => ({
  number: String(index + 1).padStart(2, "0"),
  title: item.title,
  description: item.description,
}))

const milestones = [
  { year: "2024", text: "Founded to fix how work gets done" },
  { year: "2025", text: "Private beta with enterprise partners" },
  { year: "2026", text: "Public launch", current: true },
]

// Animated connection nodes - represents AI connecting work together
function ConnectionNodes() {
  const nodes = [
    { x: "15%", y: "25%", size: 8, delay: 0 },
    { x: "85%", y: "20%", size: 6, delay: 0.5 },
    { x: "75%", y: "70%", size: 10, delay: 1 },
    { x: "20%", y: "75%", size: 6, delay: 1.5 },
    { x: "50%", y: "15%", size: 8, delay: 2 },
    { x: "40%", y: "85%", size: 6, delay: 0.8 },
  ]

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Connection lines between nodes */}
      <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="aboutLineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--success)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--success)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--success)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[
          { x1: "15%", y1: "25%", x2: "50%", y2: "15%" },
          { x1: "50%", y1: "15%", x2: "85%", y2: "20%" },
          { x1: "85%", y1: "20%", x2: "75%", y2: "70%" },
          { x1: "75%", y1: "70%", x2: "40%", y2: "85%" },
          { x1: "40%", y1: "85%", x2: "20%", y2: "75%" },
          { x1: "20%", y1: "75%", x2: "15%", y2: "25%" },
        ].map((line, i) => (
          <motion.line
            key={i}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke="url(#aboutLineGrad)"
            strokeWidth="1"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: [0, 0.6, 0] }}
            transition={{
              duration: 4,
              delay: i * 0.8,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ))}
      </svg>

      {/* Animated nodes */}
      {nodes.map((node, i) => (
        <motion.div
          key={i}
          className="absolute"
          style={{ left: node.x, top: node.y }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ 
            scale: [1, 1.2, 1],
            opacity: [0.4, 0.8, 0.4],
          }}
          transition={{
            duration: 3,
            delay: node.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div 
            className="rounded-full bg-gradient-to-br from-emerald-400 to-teal-500"
            style={{ width: node.size, height: node.size }}
          />
          <motion.div
            className="absolute inset-0 rounded-full border border-emerald-400/50"
            animate={{ scale: [1, 2.5], opacity: [0.6, 0] }}
            transition={{
              duration: 2,
              delay: node.delay,
              repeat: Infinity,
              ease: "easeOut",
            }}
            style={{ width: node.size, height: node.size }}
          />
        </motion.div>
      ))}
    </div>
  )
}

// Flowing data streams
function DataStreams() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Horizontal scan lines */}
      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/50/30 to-transparent"
        animate={{ y: [0, 800] }}
        transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-teal-400/20 to-transparent"
        animate={{ y: [800, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear", delay: 3 }}
      />
      
      {/* Radial pulse from center */}
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full border border-primary/10"
        animate={{ scale: [0.5, 2], opacity: [0.5, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut" }}
      />
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full border border-primary/10"
        animate={{ scale: [0.5, 2], opacity: [0.5, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut", delay: 2 }}
      />
    </div>
  )
}

// Floating gradient orbs
function FloatingOrbs() {
  return (
    <>
      <motion.div
        className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full bg-gradient-to-br from-emerald-200/30 to-transparent blur-3xl"
        animate={{ 
          x: [0, 60, 0],
          y: [0, 40, 0],
          scale: [1, 1.1, 1]
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-gradient-to-br from-teal-200/25 to-transparent blur-3xl"
        animate={{ 
          x: [0, -50, 0],
          y: [0, -40, 0],
          scale: [1, 1.15, 1]
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
      <motion.div
        className="absolute top-1/3 right-10 w-[300px] h-[300px] rounded-full bg-gradient-to-br from-cyan-100/20 to-transparent blur-3xl"
        animate={{ 
          x: [0, -30, 0],
          y: [0, 50, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 4 }}
      />
    </>
  )
}

export default function AboutPage() {
  return (
    <div className="bg-card">
      {/* Hero - Bold statement */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        {/* Base gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10/80 via-white to-white" />
        
        {/* Floating gradient orbs */}
        <FloatingOrbs />
        
        {/* Connection nodes animation */}
        <ConnectionNodes />
        
        {/* Data streams */}
        <DataStreams />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
        
        <div className="relative px-6 py-32 max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1 className="text-[clamp(2.5rem,8vw,6rem)] font-bold tracking-tight leading-[0.95] text-foreground">
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
            className="mt-8 text-xl sm:text-2xl text-muted-foreground max-w-2xl mx-auto font-light"
          >
            We build an intelligence engine that connects your stack, learns from verified outcomes,
            and executes through agents — with approval gates where it matters.
          </motion.p>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mt-12 flex items-center justify-center gap-6"
          >
            <Link
              href="/get-started"
              className="group inline-flex items-center gap-2 bg-foreground text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-foreground/90 hover:scale-[1.02]"
            >
              Get started
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
            </Link>
            <Link
              href="/features"
              className="group inline-flex items-center gap-2 text-muted-foreground hover:text-foreground text-sm font-medium transition-colors"
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
      <section className="border-y border-border">
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
                <div className="text-5xl sm:text-6xl font-bold text-foreground tracking-tight">
                  {stat.value}
                </div>
                <div className="mt-2 text-muted-foreground text-sm uppercase tracking-wider">
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
            <span className="text-primary text-sm font-medium uppercase tracking-wider">Our belief</span>
            <h2 className="mt-6 text-3xl sm:text-4xl lg:text-5xl font-medium text-foreground leading-[1.2]">
              Operations professionals are problem-solvers, negotiators, and strategic thinkers. 
              <span className="text-muted-foreground"> Yet most spend their days updating spreadsheets and chasing approvals.</span>
            </h2>
            <p className="mt-8 text-xl text-muted-foreground leading-relaxed">
              We built Gravitre because that&apos;s a waste of human potential. When AI handles the mechanical, 
              humans get to be human again.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Principles - Numbered list */}
      <section className="py-32 px-6 bg-muted/50">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-20"
          >
            <span className="text-primary text-sm font-medium uppercase tracking-wider">How we think</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-foreground">Our principles</h2>
          </motion.div>
          
          <div className="space-y-0">
            {principles.map((principle, i) => (
              <motion.div
                key={principle.number}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group border-t border-border py-12 flex flex-col md:flex-row md:items-center gap-6 md:gap-16"
              >
                <span className="text-primary text-sm font-mono">{principle.number}</span>
                <h3 className="text-2xl sm:text-3xl font-semibold text-foreground flex-1 group-hover:text-primary transition-colors">
                  {principle.title}
                </h3>
                <p className="text-muted-foreground md:text-right md:max-w-xs">
                  {principle.description}
                </p>
              </motion.div>
            ))}
            <div className="border-t border-border" />
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
            <span className="text-primary text-sm font-medium uppercase tracking-wider">Our journey</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold text-foreground tracking-tight">Built fast, built right</h2>
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
                <span className={`text-sm font-mono w-16 ${milestone.current ? 'text-primary' : 'text-muted-foreground'}`}>
                  {milestone.year}
                </span>
                <div className="flex items-center gap-4 flex-1">
                  <div className={`h-2 w-2 rounded-full ${milestone.current ? 'bg-primary/100' : 'bg-zinc-300'}`} />
                  <span className={`text-lg ${milestone.current ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                    {milestone.text}
                  </span>
                  {milestone.current && (
                    <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-1 rounded-full">
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
      <section className="py-32 px-6 bg-muted/50">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="inline-flex items-center gap-2 text-sm text-primary font-medium mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/100 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              We&apos;re hiring
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold text-foreground tracking-tight">
              Join the mission
            </h2>
            <p className="mt-6 text-xl text-muted-foreground max-w-xl mx-auto">
              Help us give every team their time back.
            </p>
            <Link
              href="/careers"
              className="mt-10 group inline-flex items-center gap-2 bg-foreground text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-foreground/90"
            >
              View open roles
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Final CTA - Full bleed */}
      <section className="relative py-32 lg:py-48 px-6 bg-gradient-to-b from-white to-primary/10 overflow-hidden">
        {/* Gradient accent */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-gradient-to-b from-emerald-100/50 to-transparent rounded-full blur-3xl" />
        
        <div className="relative max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground tracking-tight leading-[1.1]">
              Ready to reclaim
              <br />
              your team&apos;s time?
            </h2>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 bg-foreground text-white px-8 py-4 rounded-full text-sm font-medium transition-all hover:bg-foreground/90"
              >
                Start free trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground px-8 py-4 text-sm font-medium transition-colors"
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
