"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  ArrowRight, 
  Bot, 
  Workflow, 
  Shield, 
  Users,
  MessageSquare,
  Database,
  Zap,
  Eye,
  Lock,
  BarChart3,
  Clock,
  Check,
  GitBranch,
  Bell,
  FileText,
  Sparkles,
  ChevronRight
} from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"

// Bento card component - Light theme
function BentoCard({ 
  children, 
  className = "",
  delay = 0 
}: { 
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay }}
      className={`group relative rounded-3xl border border-zinc-200 bg-white shadow-sm overflow-hidden transition-all hover:shadow-lg hover:border-zinc-300 ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-zinc-50 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {children}
    </motion.div>
  )
}

// Feature visual component - Light theme
function FeatureVisual({ type }: { type: string }) {
  if (type === "operator") {
    return (
      <div className="relative h-full min-h-[300px] p-6 flex flex-col bg-zinc-50/50">
        <div className="flex-1 space-y-4">
          {/* Chat interface */}
          <motion.div 
            className="flex items-start gap-3"
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <div className="h-8 w-8 rounded-full bg-zinc-200 flex items-center justify-center shrink-0">
              <div className="h-4 w-4 rounded-full bg-zinc-400" />
            </div>
            <div className="flex-1 rounded-2xl rounded-tl-sm bg-zinc-100 p-4">
              <p className="text-sm text-zinc-600">Show me all failed workflows from the past week</p>
            </div>
          </motion.div>
          
          <motion.div 
            className="flex items-start gap-3 justify-end"
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4 }}
          >
            <div className="flex-1 rounded-2xl rounded-tr-sm bg-gradient-to-br from-emerald-50 to-emerald-100 border border-emerald-200 p-4">
              <p className="text-sm text-emerald-800">Found 3 failed workflows. The main issue appears to be API rate limiting on the Salesforce connector...</p>
            </div>
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shrink-0 shadow-md">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
          </motion.div>
        </div>
        
        {/* Input */}
        <div className="mt-4 rounded-xl border border-zinc-200 bg-white p-3 flex items-center gap-3 shadow-sm">
          <div className="flex-1">
            <div className="h-4 w-32 rounded bg-zinc-100" />
          </div>
          <div className="h-8 w-8 rounded-lg bg-emerald-500 flex items-center justify-center">
            <ArrowRight className="h-4 w-4 text-white" />
          </div>
        </div>
      </div>
    )
  }

  if (type === "agents") {
    return (
      <div className="relative h-full min-h-[300px] p-6 bg-zinc-50/50">
        <div className="grid grid-cols-2 gap-4 h-full">
          {[
            { name: "Data Analyst", color: "emerald", icon: BarChart3, status: "active" },
            { name: "Content Writer", color: "blue", icon: FileText, status: "active" },
            { name: "Research Agent", color: "purple", icon: Eye, status: "idle" },
            { name: "Code Reviewer", color: "amber", icon: GitBranch, status: "active" },
          ].map((agent, i) => (
            <motion.div
              key={agent.name}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="rounded-xl border border-zinc-200 bg-white p-4 flex flex-col items-center justify-center text-center shadow-sm"
            >
              <div className={`h-12 w-12 rounded-full flex items-center justify-center mb-3 relative ${
                agent.color === 'emerald' ? 'bg-emerald-100' :
                agent.color === 'blue' ? 'bg-blue-100' :
                agent.color === 'purple' ? 'bg-purple-100' : 'bg-amber-100'
              }`}>
                <agent.icon className={`h-6 w-6 ${
                  agent.color === 'emerald' ? 'text-emerald-600' :
                  agent.color === 'blue' ? 'text-blue-600' :
                  agent.color === 'purple' ? 'text-purple-600' : 'text-amber-600'
                }`} />
                {agent.status === "active" && (
                  <motion.div
                    className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full ring-2 ring-white ${
                      agent.color === 'emerald' ? 'bg-emerald-500' :
                      agent.color === 'blue' ? 'bg-blue-500' :
                      agent.color === 'purple' ? 'bg-purple-500' : 'bg-amber-500'
                    }`}
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                )}
              </div>
              <span className="text-xs font-medium text-zinc-900">{agent.name}</span>
              <span className={`text-[10px] ${agent.status === "active" ? "text-emerald-600" : "text-zinc-400"}`}>
                {agent.status}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    )
  }

  if (type === "workflows") {
    return (
      <div className="relative h-full min-h-[300px] p-6 flex items-center justify-center bg-zinc-50/50">
        <div className="flex items-center gap-3">
          {[
            { icon: Database, color: "blue" },
            { icon: Bot, color: "emerald" },
            { icon: Users, color: "purple" },
            { icon: BarChart3, color: "amber" },
          ].map((node, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15, type: "spring" }}
              className="flex items-center"
            >
              <div className={`h-14 w-14 rounded-xl border shadow-sm flex items-center justify-center ${
                node.color === 'blue' ? 'border-blue-200 bg-blue-50' :
                node.color === 'emerald' ? 'border-emerald-200 bg-emerald-50' :
                node.color === 'purple' ? 'border-purple-200 bg-purple-50' : 'border-amber-200 bg-amber-50'
              }`}>
                <node.icon className={`h-6 w-6 ${
                  node.color === 'blue' ? 'text-blue-600' :
                  node.color === 'emerald' ? 'text-emerald-600' :
                  node.color === 'purple' ? 'text-purple-600' : 'text-amber-600'
                }`} />
              </div>
              {i < 3 && (
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: 32 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.15 + 0.2 }}
                  className="h-0.5 bg-gradient-to-r from-zinc-300 to-zinc-200"
                />
              )}
            </motion.div>
          ))}
        </div>
      </div>
    )
  }

  if (type === "governance") {
    return (
      <div className="relative h-full min-h-[300px] p-6 space-y-3 bg-zinc-50/50">
        {[
          { icon: Lock, label: "Role-based access control", status: true },
          { icon: FileText, label: "Complete audit trail", status: true },
          { icon: Shield, label: "SOC 2 Type II certified", status: true },
          { icon: Check, label: "Human-in-the-loop approvals", status: true },
        ].map((item, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <item.icon className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-zinc-900">{item.label}</span>
            </div>
            <div className="h-6 w-6 rounded-full bg-emerald-100 flex items-center justify-center">
              <Check className="h-3 w-3 text-emerald-600" />
            </div>
          </motion.div>
        ))}
      </div>
    )
  }

  return null
}

export default function FeaturesPage() {
  return (
    <div className="relative overflow-hidden bg-white">
      {/* Hero */}
      <section className="relative py-32 overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-transparent to-transparent" />
        
        {/* Animated floating orbs */}
        <motion.div 
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-emerald-100 rounded-full blur-3xl"
          animate={{ 
            scale: [1, 1.15, 1],
            opacity: [0.3, 0.4, 0.3],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div 
          className="absolute top-20 -left-32 w-[400px] h-[400px] bg-blue-100 rounded-full blur-3xl"
          animate={{ 
            x: [0, 50, 0],
            opacity: [0.2, 0.3, 0.2],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />
        <motion.div 
          className="absolute top-40 -right-32 w-[350px] h-[350px] bg-purple-100 rounded-full blur-3xl"
          animate={{ 
            x: [0, -30, 0],
            opacity: [0.15, 0.25, 0.15],
          }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut", delay: 4 }}
        />
        
        {/* Neural connection lines */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.05]" xmlns="http://www.w3.org/2000/svg">
          {Array.from({ length: 6 }).map((_, i) => (
            <motion.line
              key={i}
              x1={`${15 + i * 15}%`}
              y1="0%"
              x2={`${25 + i * 10}%`}
              y2="100%"
              stroke="#10b981"
              strokeWidth="1"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: [0, 1, 0] }}
              transition={{
                duration: 5,
                delay: i * 0.8,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </svg>
        
        {/* Floating icons */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[
            { icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5", left: "15%", top: "20%", delay: 0 },
            { icon: "M20 7h-9M14 17H5M17 17a2 2 0 100-4 2 2 0 000 4zM7 7a2 2 0 100-4 2 2 0 000 4z", left: "80%", top: "30%", delay: 1 },
            { icon: "M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6", left: "10%", top: "70%", delay: 2 },
          ].map((item, i) => (
            <motion.div
              key={i}
              className="absolute w-12 h-12 rounded-xl bg-white/60 backdrop-blur-sm border border-emerald-200/50 flex items-center justify-center shadow-sm"
              style={{ left: item.left, top: item.top }}
              animate={{ 
                y: [0, -15, 0],
                rotate: [0, 5, 0],
              }}
              transition={{
                duration: 6,
                delay: item.delay,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
            </motion.div>
          ))}
        </div>
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-3xl text-center"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 backdrop-blur-sm px-4 py-2"
            >
              <motion.div
                animate={{ rotate: [0, 360] }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              >
                <Sparkles className="h-4 w-4 text-emerald-600" />
              </motion.div>
              <span className="text-sm font-medium text-emerald-700">Powerful capabilities</span>
            </motion.div>
            
            {/* Staggered headline */}
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight"
              >
                <span className="text-zinc-900">
                  Everything you need
                </span>
              </motion.h1>
            </div>
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent"
              >
                to work with AI
              </motion.h1>
            </div>
            
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto"
            >
              A simple platform to set up, manage, and keep your AI team running smoothly.
            </motion.p>
            
            {/* Feature pills */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="mt-10 flex flex-wrap items-center justify-center gap-3"
            >
              {["AI Assistant", "Smart Agents", "Workflows", "Integrations", "Analytics"].map((feature, i) => (
                <motion.span
                  key={feature}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 + i * 0.1 }}
                  className="px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-zinc-200 text-sm font-medium text-zinc-700 shadow-sm"
                >
                  {feature}
                </motion.span>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Bento Grid */}
      <section className="relative pb-32">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* AI Assistant - Large card */}
            <BentoCard className="lg:col-span-2 lg:row-span-2" delay={0}>
              <div className="p-8">
                <div className="flex items-center gap-4 mb-4">
                  <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-50 ring-1 ring-emerald-200 flex items-center justify-center">
                    <Bot className="h-6 w-6 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-zinc-900">AI Assistant</h3>
                    <p className="text-sm text-emerald-600">Your control center</p>
                  </div>
                </div>
                <p className="text-zinc-600 max-w-lg">
                  Talk to your AI team in plain English. Ask questions, start tasks, and get instant answers.
                </p>
              </div>
              <FeatureVisual type="operator" />
            </BentoCard>

            {/* Agents - Medium card */}
            <BentoCard delay={0.1}>
              <div className="p-6">
                <div className="flex items-center gap-3 mb-3">
                  <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <Users className="h-5 w-5 text-blue-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Smart Agents</h3>
                </div>
                <p className="text-sm text-zinc-600">Ready-made AI helpers for every part of your business.</p>
              </div>
              <FeatureVisual type="agents" />
            </BentoCard>

            {/* Automations - Medium card */}
            <BentoCard delay={0.2}>
              <div className="p-6">
                <div className="flex items-center gap-3 mb-3">
                  <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                    <Workflow className="h-5 w-5 text-purple-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Easy Automations</h3>
                </div>
                <p className="text-sm text-zinc-600">Build powerful automations by dragging and dropping.</p>
              </div>
              <FeatureVisual type="workflows" />
            </BentoCard>

            {/* Safety - Wide card */}
            <BentoCard className="lg:col-span-2" delay={0.3}>
              <div className="grid lg:grid-cols-2">
                <div className="p-8">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
                      <Shield className="h-5 w-5 text-amber-600" />
                    </div>
                    <h3 className="text-lg font-semibold text-zinc-900">Built-in Safety</h3>
                  </div>
                  <p className="text-zinc-600 mb-6">
                    Control who can do what, keep a full history, and require approval before big changes.
                  </p>
                  <Link 
                    href="/security"
                    className="inline-flex items-center gap-2 text-sm text-amber-600 hover:text-amber-700 transition-colors font-medium"
                  >
                    Learn about security
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </div>
                <FeatureVisual type="governance" />
              </div>
            </BentoCard>

            {/* Live View - Small card */}
            <BentoCard delay={0.4}>
              <div className="p-6 h-full flex flex-col">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-rose-100 flex items-center justify-center">
                    <Zap className="h-5 w-5 text-rose-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-900">Live View</h3>
                </div>
                <p className="text-sm text-zinc-600 flex-1">
                  Watch your automations run in real-time. Pause, fix issues, and undo changes easily.
                </p>
                <div className="mt-6 flex items-center gap-2">
                  <motion.div
                    className="h-2 w-2 rounded-full bg-emerald-500"
                    animate={{ opacity: [1, 0.5, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                  <span className="text-xs text-emerald-600 font-medium">Live monitoring</span>
                </div>
              </div>
            </BentoCard>
          </div>
        </div>
      </section>

      {/* Detailed Features */}
      <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Capabilities that scale
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              Every feature designed for enterprise requirements.
            </p>
          </motion.div>

          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: MessageSquare, title: "Natural Language", description: "Control everything with simple commands" },
              { icon: Eye, title: "Full Visibility", description: "See reasoning steps and data flows" },
              { icon: Bell, title: "Smart Alerts", description: "Proactive notifications when needed" },
              { icon: Clock, title: "Instant Insights", description: "Get answers in seconds, not hours" },
              { icon: Database, title: "100+ Integrations", description: "Connect all your tools instantly" },
              { icon: GitBranch, title: "Version Control", description: "Track and rollback changes" },
              { icon: Lock, title: "SSO & SAML", description: "Enterprise authentication" },
              { icon: BarChart3, title: "Analytics", description: "Deep insights into performance" },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="text-center"
              >
                <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-white border border-zinc-200 shadow-sm flex items-center justify-center">
                  <feature.icon className="h-5 w-5 text-zinc-600" />
                </div>
                <h3 className="text-sm font-semibold text-zinc-900">{feature.title}</h3>
                <p className="mt-1 text-xs text-zinc-500">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations - Now with real logos */}
      <section className="relative py-32 border-t border-zinc-200">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Connects to your entire stack
            </h2>
            <p className="mt-4 text-zinc-600">
              100+ pre-built integrations with the tools you already use.
            </p>
          </motion.div>

          <IntegrationsGrid theme="light" />
        </div>
      </section>

      {/* CTA */}
      <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-50 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center"
          >
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">
              Ready to get started?
            </h2>
            <p className="mt-4 text-zinc-600">
              Start your free trial today. No credit card required.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800"
              >
                Start free trial
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-4 text-base font-semibold text-zinc-900 transition-all hover:bg-zinc-50"
              >
                Talk to sales
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
