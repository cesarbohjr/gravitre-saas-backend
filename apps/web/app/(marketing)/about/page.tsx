"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Linkedin, Twitter } from "lucide-react"

const team = [
  {
    name: "Sarah Chen",
    role: "CEO & Co-founder",
    bio: "Previously VP Engineering at Stripe. Stanford CS.",
    image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=400&h=400&fit=crop&crop=face",
  },
  {
    name: "Marcus Rodriguez",
    role: "CTO & Co-founder",
    bio: "Ex-Google DeepMind. PhD in Machine Learning from MIT.",
    image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop&crop=face",
  },
  {
    name: "Emily Watson",
    role: "VP Product",
    bio: "Previously Product Lead at Notion. Loves solving complex UX.",
    image: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=400&fit=crop&crop=face",
  },
  {
    name: "David Kim",
    role: "VP Engineering",
    bio: "Built infra at Scale AI. Obsessed with reliability.",
    image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop&crop=face",
  },
  {
    name: "Priya Patel",
    role: "VP Design",
    bio: "Ex-Figma design systems. Crafting intuitive AI experiences.",
    image: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop&crop=face",
  },
  {
    name: "Alex Thompson",
    role: "VP Sales",
    bio: "Scaled enterprise teams at Databricks and Snowflake.",
    image: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop&crop=face",
  },
]

const investors = [
  { name: "Sequoia Capital", logo: "Sequoia" },
  { name: "Andreessen Horowitz", logo: "a16z" },
  { name: "Accel", logo: "Accel" },
  { name: "Index Ventures", logo: "Index" },
]

const values = [
  {
    title: "Move fast with intention",
    description: "We ship quickly but never compromise on quality. Every feature is designed with purpose.",
  },
  {
    title: "Trust through transparency",
    description: "AI should be explainable. We build tools that show their work and earn user confidence.",
  },
  {
    title: "Empower, don&apos;t replace",
    description: "Our AI augments human capability. We believe in collaboration, not automation for its own sake.",
  },
  {
    title: "Enterprise-grade, startup-fast",
    description: "Security and compliance at scale, with the agility and innovation of a startup.",
  },
]

const timeline = [
  { year: "2022", event: "Founded in San Francisco by Sarah & Marcus" },
  { year: "2023", event: "Raised $25M Series A led by Sequoia" },
  { year: "2024", event: "Launched AI Operator, reached 100 customers" },
  { year: "2025", event: "Raised $80M Series B, expanded to 500+ customers" },
  { year: "2026", event: "10M+ tasks automated monthly, global expansion" },
]

export default function AboutPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-40">
        {/* Animated background */}
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-white to-transparent" />
        
        {/* Floating orbs */}
        <motion.div 
          className="absolute top-20 left-1/4 w-[400px] h-[400px] bg-emerald-200 rounded-full blur-3xl"
          animate={{ 
            y: [0, -30, 0],
            opacity: [0.2, 0.3, 0.2],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div 
          className="absolute top-40 right-1/4 w-[300px] h-[300px] bg-blue-100 rounded-full blur-3xl"
          animate={{ 
            y: [0, 30, 0],
            opacity: [0.15, 0.25, 0.15],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />
        
        {/* Particle dots */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {Array.from({ length: 20 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1.5 h-1.5 bg-emerald-500/20 rounded-full"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
              }}
              animate={{
                y: [0, -20, 0],
                opacity: [0.2, 0.5, 0.2],
              }}
              transition={{
                duration: 4 + Math.random() * 4,
                repeat: Infinity,
                delay: Math.random() * 2,
              }}
            />
          ))}
        </div>
        
        <div className="relative mx-auto max-w-4xl text-center">
          {/* Animated badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="mb-8"
          >
            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100/80 backdrop-blur-sm px-4 py-2 text-sm font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <motion.div 
                className="h-2 w-2 rounded-full bg-emerald-500"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              About Gravitre
            </span>
          </motion.div>
          
          {/* Staggered headline */}
          <div className="overflow-hidden">
            <motion.h1
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
              className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl"
            >
              Building the future of
            </motion.h1>
          </div>
          <div className="overflow-hidden">
            <motion.h1
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent"
            >
              AI-powered operations
            </motion.h1>
          </div>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mt-8 text-lg text-zinc-600 max-w-2xl mx-auto leading-relaxed"
          >
            We&apos;re on a mission to help every organization harness the power of AI to automate complex workflows, 
            eliminate manual work, and focus on what truly matters.
          </motion.p>
          
          {/* Stats preview */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="mt-12 flex flex-wrap items-center justify-center gap-8"
          >
            {[
              { value: "2022", label: "Founded" },
              { value: "500+", label: "Customers" },
              { value: "10M+", label: "Tasks/month" },
            ].map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.7 + i * 0.1 }}
                className="px-6 py-3 rounded-2xl bg-white/80 backdrop-blur-sm border border-zinc-200 shadow-sm"
              >
                <div className="text-2xl font-bold text-zinc-900">{stat.value}</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wide">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Mission */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-24 items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <h2 className="text-3xl font-semibold text-zinc-900 mb-6">Our Mission</h2>
              <p className="text-zinc-600 mb-4">
                Every day, millions of hours are lost to repetitive, manual tasks that drain teams and slow down businesses. 
                We founded Gravitre to change that.
              </p>
              <p className="text-zinc-600 mb-4">
                Our platform enables businesses to deploy AI agents that work alongside human teams, handling everything from 
                data synchronization to complex multi-step workflows. We believe AI should be a force multiplier for human 
                creativity and decision-making, not a replacement for it.
              </p>
              <p className="text-zinc-600">
                With Gravitre, enterprises can finally realize the promise of AI: intelligent automation that&apos;s secure, 
                explainable, and genuinely helpful.
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="relative"
            >
              <div className="aspect-video rounded-2xl bg-gradient-to-br from-emerald-100 to-zinc-100 border border-zinc-200 flex items-center justify-center shadow-lg">
                <div className="text-center p-8">
                  <div className="text-5xl font-bold text-zinc-900 mb-2">10M+</div>
                  <div className="text-sm text-zinc-500">Tasks automated monthly</div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Our Values</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              The principles that guide everything we build and how we work together.
            </p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2">
            {values.map((value, i) => (
              <motion.div
                key={value.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm"
              >
                <h3 className="text-lg font-medium text-zinc-900 mb-2">{value.title}</h3>
                <p className="text-sm text-zinc-600">{value.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Timeline */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Our Journey</h2>
          </motion.div>
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-zinc-200" />
            <div className="space-y-8">
              {timeline.map((item, i) => (
                <motion.div
                  key={item.year}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="relative pl-12"
                >
                  <div className="absolute left-0 top-1 h-8 w-8 rounded-full bg-white border border-zinc-200 flex items-center justify-center shadow-sm">
                    <div className="h-2 w-2 rounded-full bg-emerald-500" />
                  </div>
                  <div className="text-sm text-emerald-600 font-medium">{item.year}</div>
                  <div className="text-zinc-900 mt-1">{item.event}</div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Leadership Team</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              Veterans from the world&apos;s best technology companies, united by a shared vision.
            </p>
          </motion.div>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {team.map((member, i) => (
              <motion.div
                key={member.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group relative rounded-2xl border border-zinc-200 bg-white p-6 transition-all hover:border-emerald-300 hover:shadow-md"
              >
                <img
                  src={member.image}
                  alt={member.name}
                  className="h-20 w-20 rounded-full object-cover mb-4"
                />
                <h3 className="text-lg font-medium text-zinc-900">{member.name}</h3>
                <p className="text-sm text-emerald-600">{member.role}</p>
                <p className="text-sm text-zinc-500 mt-2">{member.bio}</p>
                <div className="flex gap-3 mt-4">
                  <a href={`https://twitter.com/${member.name.toLowerCase().replace(/\s+/g, '')}`} target="_blank" rel="noopener noreferrer" className="text-zinc-400 hover:text-zinc-900 transition-colors">
                    <Twitter className="h-4 w-4" />
                  </a>
                  <a href={`https://linkedin.com/in/${member.name.toLowerCase().replace(/\s+/g, '-')}`} target="_blank" rel="noopener noreferrer" className="text-zinc-400 hover:text-zinc-900 transition-colors">
                    <Linkedin className="h-4 w-4" />
                  </a>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Investors */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-8">Backed by the best</h2>
            <div className="flex flex-wrap items-center justify-center gap-12">
              {investors.map((investor) => (
                <div key={investor.name} className="text-xl font-medium text-zinc-400">
                  {investor.logo}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Join us</h2>
            <p className="text-zinc-600 mb-8 max-w-xl mx-auto">
              We&apos;re building the future of AI operations. Come help us shape it.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/careers"
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
              >
                View open roles
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100"
              >
                Get in touch
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
