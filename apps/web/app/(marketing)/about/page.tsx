"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Linkedin, Twitter } from "lucide-react"

const founder = {
  name: "Cesar Bohorquez Jr",
  role: "Founder & CEO",
  bio: "Serial entrepreneur and technologist with a passion for building products that empower businesses through intelligent automation. Previously founded and scaled multiple technology ventures. Now focused on democratizing AI operations for enterprises of all sizes.",
  image: "/images/team/cesar-bohorquez.jpg",
  linkedin: "https://www.linkedin.com/in/cesarbohorquezjr/",
  twitter: "https://twitter.com/cesarbohorquezjr",
  imageStyle: { objectPosition: "center 15%" },
}

const investors: { name: string; logo: string }[] = []

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
  { year: "2024", event: "Founded by Cesar Bohorquez Jr with a vision to democratize AI operations" },
  { year: "2025", event: "Launched Gravitre AI Operator platform in private beta" },
  { year: "2026", event: "Public launch and growing customer base" },
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
        
        {/* Particle dots - fixed positions */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[
            { left: '10%', top: '20%', dur: 5 }, { left: '25%', top: '15%', dur: 6 },
            { left: '40%', top: '30%', dur: 4 }, { left: '60%', top: '10%', dur: 7 },
            { left: '75%', top: '25%', dur: 5 }, { left: '85%', top: '35%', dur: 6 },
            { left: '15%', top: '50%', dur: 4 }, { left: '30%', top: '60%', dur: 5 },
            { left: '50%', top: '45%', dur: 6 }, { left: '70%', top: '55%', dur: 4 },
          ].map((p, i) => (
            <motion.div
              key={i}
              className="absolute w-1.5 h-1.5 bg-emerald-500/20 rounded-full"
              style={{ left: p.left, top: p.top }}
              animate={{
                y: [0, -20, 0],
                opacity: [0.2, 0.5, 0.2],
              }}
              transition={{
                duration: p.dur,
                repeat: Infinity,
                delay: i * 0.2,
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
              { value: "2024", label: "Founded" },
              { value: "100%", label: "Founder-led" },
              { value: "Enterprise", label: "Ready" },
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
                  <div className="text-4xl font-bold text-zinc-900 mb-2">AI-First</div>
                  <div className="text-sm text-zinc-500">Built for the future of work</div>
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

      {/* Founder */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Meet the Founder</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              Building the future of AI-powered operations, one automation at a time.
            </p>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex flex-col md:flex-row items-center gap-8 md:gap-12"
          >
            <div className="flex-shrink-0">
              <img
                src={founder.image}
                alt={founder.name}
                className="h-48 w-48 rounded-2xl object-cover shadow-lg border border-zinc-200"
                style={founder.imageStyle}
              />
            </div>
            <div className="text-center md:text-left">
              <h3 className="text-2xl font-semibold text-zinc-900">{founder.name}</h3>
              <p className="text-emerald-600 font-medium mt-1">{founder.role}</p>
              <p className="text-zinc-600 mt-4 leading-relaxed">{founder.bio}</p>
              <div className="flex items-center justify-center md:justify-start gap-4 mt-6">
                <a 
                  href={founder.twitter} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 transition-colors"
                >
                  <Twitter className="h-4 w-4" />
                  Twitter
                </a>
                <a 
                  href={founder.linkedin} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 transition-colors"
                >
                  <Linkedin className="h-4 w-4" />
                  LinkedIn
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Hiring CTA */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-100 p-8 md:p-12 text-center"
          >
            <h3 className="text-2xl font-semibold text-zinc-900 mb-3">We&apos;re Building the Team</h3>
            <p className="text-zinc-600 max-w-xl mx-auto mb-6">
              Gravitre is growing. We&apos;re looking for passionate engineers, designers, and operators 
              who want to shape the future of AI automation.
            </p>
            <Link
              href="/careers"
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-700"
            >
              View Open Positions
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Investors - only show if we have investors */}
      {investors.length > 0 && (
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
      )}

      {/* CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Ready to get started?</h2>
            <p className="text-zinc-600 mb-8 max-w-xl mx-auto">
              See how Gravitre can transform your operations with AI-powered automation.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
              >
                Start free trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100"
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
