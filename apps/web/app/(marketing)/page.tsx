"use client"

import Link from "next/link"
import { motion, useScroll, useTransform, useMotionValue, useSpring, AnimatePresence } from "framer-motion"
import { useRef, useEffect, useState } from "react"
import { ArrowRight, Bot, Workflow, Shield, Zap, Users, BarChart3, Sparkles, Play, ChevronRight, Activity, Cpu, Globe } from "lucide-react"
import { AppShowcase } from "@/components/gravitre/app-showcase"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { ProductShowcase, HowItWorks, TestimonialsCarousel, AnimatedStats } from "@/components/marketing/product-showcase"
import { IntelligenceEngineSection } from "@/components/marketing/intelligence-engine-section"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"

// Interactive particle field
function seededUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

function ParticleField() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 50 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-emerald-500/30 rounded-full"
          initial={{
            x: `${seededUnit(i + 1) * 100}%`,
            y: `${seededUnit(i + 101) * 100}%`,
            scale: seededUnit(i + 201) * 0.5 + 0.5,
          }}
          animate={{
            y: [`${seededUnit(i + 301) * 100}%`, `${seededUnit(i + 401) * 100}%`],
            x: [`${seededUnit(i + 501) * 100}%`, `${seededUnit(i + 601) * 100}%`],
            opacity: [0.2, 0.6, 0.2],
          }}
          transition={{
            duration: seededUnit(i + 701) * 20 + 10,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      ))}
    </div>
  )
}

// Floating orb component with mouse interaction
function FloatingOrb({ className, delay = 0 }: { className: string; delay?: number }) {
  return (
    <motion.div
      className={`absolute rounded-full blur-3xl ${className}`}
      animate={{
        y: [0, -30, 0],
        scale: [1, 1.1, 1],
        opacity: [0.2, 0.3, 0.2],
      }}
      transition={{
        duration: 8,
        delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  )
}

// Neural network connection lines
function NeuralLines() {
  return (
    <svg className="absolute inset-0 w-full h-full opacity-[0.07]" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--success)" stopOpacity="0" />
          <stop offset="50%" stopColor="var(--success)" stopOpacity="1" />
          <stop offset="100%" stopColor="var(--success)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {Array.from({ length: 8 }).map((_, i) => (
        <motion.line
          key={i}
          x1={`${10 + i * 12}%`}
          y1="0%"
          x2={`${30 + i * 8}%`}
          y2="100%"
          stroke="url(#lineGrad)"
          strokeWidth="1"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: [0, 0.5, 0] }}
          transition={{
            duration: 4,
            delay: i * 0.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </svg>
  )
}

// Live system metrics display
function LiveMetrics() {
  const [metrics, setMetrics] = useState({
    tasks: 1247,
    agents: 4,
    uptime: 99.9,
  })
  
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        tasks: prev.tasks + Math.floor(Math.random() * 3),
        agents: prev.agents,
        uptime: 99.9,
      }))
    }, 2000)
    return () => clearInterval(interval)
  }, [])
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.2 }}
      className="flex flex-wrap items-center justify-center gap-3 sm:gap-6 lg:gap-8 mt-10 sm:mt-16 px-4"
    >
      {[
        { icon: Activity, label: "Tasks/day", value: metrics.tasks.toLocaleString(), color: "emerald" },
        { icon: Cpu, label: "Active agents", value: metrics.agents, color: "blue" },
        { icon: Globe, label: "Uptime", value: `${metrics.uptime}%`, color: "purple" },
      ].map((metric, i) => (
        <motion.div
          key={metric.label}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.3 + i * 0.1 }}
          className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2 rounded-full bg-white/80 backdrop-blur-sm border border-zinc-200 shadow-sm"
        >
          <div className={`p-1 sm:p-1.5 rounded-full ${
            metric.color === 'emerald' ? 'bg-emerald-100' :
            metric.color === 'blue' ? 'bg-blue-100' : 'bg-purple-100'
          }`}>
            <metric.icon strokeWidth={1.5} className={`h-3 w-3 sm:h-3.5 sm:w-3.5 ${
              metric.color === 'emerald' ? 'text-emerald-600' :
              metric.color === 'blue' ? 'text-blue-600' : 'text-purple-600'
            }`} />
          </div>
          <div className="text-left">
            <div className="text-xs sm:text-sm font-semibold text-zinc-900">{metric.value}</div>
            <div className="text-[9px] sm:text-[10px] text-zinc-500 uppercase tracking-wide">{metric.label}</div>
          </div>
        </motion.div>
      ))}
    </motion.div>
  )
}

// Animated grid background - Light theme with enhanced effects
function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Gradient mesh background */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/80 via-white to-blue-50/50" />
      
      {/* Animated gradient orbs */}
      <motion.div
        className="absolute top-0 left-1/4 w-[600px] h-[600px] rounded-full bg-gradient-to-br from-emerald-200/40 to-transparent blur-3xl"
        animate={{ 
          x: [0, 100, 0],
          y: [0, 50, 0],
          scale: [1, 1.1, 1]
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 right-1/4 w-[500px] h-[500px] rounded-full bg-gradient-to-br from-blue-200/30 to-transparent blur-3xl"
        animate={{ 
          x: [0, -80, 0],
          y: [0, -60, 0],
          scale: [1, 1.2, 1]
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
      <motion.div
        className="absolute top-1/3 right-0 w-[400px] h-[400px] rounded-full bg-gradient-to-br from-purple-100/30 to-transparent blur-3xl"
        animate={{ 
          x: [0, -50, 0],
          y: [0, 100, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 4 }}
      />
      
      {/* Grid pattern */}
      <div 
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)
          `,
          backgroundSize: '64px 64px',
        }}
      />
      
      <NeuralLines />
      
      {/* Multiple scan lines */}
      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"
        animate={{ y: [0, 1000] }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/20 to-transparent"
        animate={{ y: [0, 1000] }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear", delay: 4 }}
      />
      
      {/* Multiple radial pulses */}
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full border border-emerald-500/10"
        animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut" }}
      />
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full border border-emerald-500/10"
        animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut", delay: 2 }}
      />
      
      {/* Floating particles - fixed positions to avoid hydration issues */}
      {[
        { left: '10%', top: '20%', dur: 5 }, { left: '25%', top: '15%', dur: 6 },
        { left: '40%', top: '30%', dur: 4 }, { left: '60%', top: '10%', dur: 7 },
        { left: '75%', top: '25%', dur: 5 }, { left: '85%', top: '35%', dur: 6 },
        { left: '15%', top: '50%', dur: 4 }, { left: '30%', top: '60%', dur: 5 },
        { left: '50%', top: '45%', dur: 6 }, { left: '70%', top: '55%', dur: 4 },
        { left: '90%', top: '50%', dur: 7 }, { left: '5%', top: '70%', dur: 5 },
        { left: '20%', top: '80%', dur: 6 }, { left: '45%', top: '75%', dur: 4 },
        { left: '65%', top: '85%', dur: 5 }, { left: '80%', top: '70%', dur: 6 },
      ].map((p, i) => (
        <motion.div
          key={i}
          className="absolute w-1.5 h-1.5 bg-emerald-400/50 rounded-full"
          style={{ left: p.left, top: p.top }}
          animate={{
            y: [0, -25, 0],
            opacity: [0.3, 0.7, 0.3],
            scale: [1, 1.3, 1],
          }}
          transition={{
            duration: p.dur,
            repeat: Infinity,
            delay: i * 0.3,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

// Animated stats counter - Light theme
function AnimatedStat({ value, label, suffix = "" }: { value: string; label: string; suffix?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="relative group"
    >
      <div className="absolute -inset-4 rounded-2xl bg-gradient-to-b from-emerald-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative text-center">
        <motion.div 
          className="text-5xl sm:text-6xl font-bold text-zinc-900"
          whileInView={{ scale: [0.5, 1] }}
          transition={{ type: "spring", stiffness: 200 }}
        >
          {value}{suffix}
        </motion.div>
        <div className="mt-2 text-sm text-zinc-500">{label}</div>
      </div>
    </motion.div>
  )
}

// Feature card with hover effect - Light theme
function FeatureCard({ 
  icon: Icon, 
  title, 
  description, 
  index 
}: { 
  icon: React.ElementType
  title: string
  description: string
  index: number 
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.1 }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="group relative"
    >
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-emerald-100 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <div className="relative h-full rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-all group-hover:border-zinc-300 group-hover:shadow-lg">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-50 ring-1 ring-emerald-200 group-hover:ring-emerald-300 transition-all">
          <Icon className="h-6 w-6 text-emerald-600" strokeWidth={1.5} />
        </div>
        <h3 className="text-lg font-semibold text-zinc-900 group-hover:text-emerald-900 transition-colors">{title}</h3>
        <p className="mt-2 text-sm text-zinc-600 leading-relaxed">{description}</p>
        <div className="mt-4 flex items-center text-sm text-emerald-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          <span>Learn more</span>
          <ChevronRight strokeWidth={1.5} className="ml-1 h-4 w-4" />
        </div>
      </div>
    </motion.div>
  )
}

// Product preview with parallax - Light theme
function ProductPreview() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"]
  })
  const y = useTransform(scrollYProgress, [0, 1], [100, -100])
  const opacity = useTransform(scrollYProgress, [0, 0.3, 0.7, 1], [0, 1, 1, 0])

  return (
    <motion.div ref={ref} style={{ y, opacity }} className="relative">
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-b from-emerald-200/30 via-transparent to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-zinc-200 bg-white p-2 shadow-2xl">
        <div className="rounded-xl border border-zinc-100 bg-zinc-50 overflow-hidden">
          {/* Browser chrome */}
          <div className="flex items-center gap-2 border-b border-zinc-200 bg-white px-4 py-3">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-400" />
              <div className="h-3 w-3 rounded-full bg-yellow-400" />
              <div className="h-3 w-3 rounded-full bg-green-400" />
            </div>
            <div className="flex-1 text-center">
              <span className="text-xs text-zinc-400 font-mono">gravitre.app/ai</span>
            </div>
          </div>
          {/* App content */}
          <div className="aspect-[16/9] bg-gradient-to-br from-zinc-50 to-white p-6 sm:p-8">
            <div className="grid h-full grid-cols-12 gap-4">
              {/* Sidebar */}
              <div className="col-span-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                <div className="space-y-3">
                  {[1,2,3,4,5].map(i => (
                    <motion.div 
                      key={i} 
                      className="flex items-center gap-2"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                    >
                      <div className={`h-2 w-2 rounded-full ${i === 2 ? 'bg-emerald-500' : 'bg-zinc-300'}`} />
                      <div className={`h-2 rounded ${i === 2 ? 'w-16 bg-zinc-400' : 'w-12 bg-zinc-200'}`} />
                    </motion.div>
                  ))}
                </div>
              </div>
              {/* Main content */}
              <div className="col-span-6 space-y-4">
                <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <motion.div 
                      className="h-10 w-10 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-md"
                      animate={{ scale: [1, 1.05, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    >
                      <Sparkles strokeWidth={1.5} className="h-5 w-5 text-white" />
                    </motion.div>
                    <div className="flex-1">
                      <div className="h-2 w-32 rounded bg-zinc-300" />
                      <div className="mt-1 h-2 w-24 rounded bg-zinc-200" />
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                  <motion.div
                    className="h-2 w-full rounded bg-emerald-300"
                    animate={{ width: ["0%", "100%"] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </div>
              </div>
              {/* Right panel */}
              <div className="col-span-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-zinc-400 mb-3 font-medium">Metrics</div>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-500">Success</span>
                      <span className="text-emerald-600 font-medium">98.5%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-100">
                      <motion.div 
                        className="h-full rounded-full bg-emerald-500"
                        initial={{ width: 0 }}
                        animate={{ width: "98.5%" }}
                        transition={{ duration: 1, delay: 0.5 }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default function HomePage() {
  const heroRef = useRef(null)
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"]
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.95])
  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, 100])

  return (
    <div className="relative overflow-hidden bg-white">
      {/* Hero Section */}
      <section ref={heroRef} className="relative min-h-screen flex items-center justify-center">
        <GridBackground />
        
        <motion.div 
          style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
          className="relative mx-auto max-w-7xl px-6 py-32 sm:py-40"
        >
          <div className="mx-auto max-w-4xl text-center">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="mb-8 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 backdrop-blur-sm px-4 py-2"
            >
              <motion.div 
                className="h-2 w-2 rounded-full bg-emerald-500"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <span className="text-sm font-medium text-emerald-700">{MARKETING_COPY.hero.badge}</span>
              <ChevronRight strokeWidth={1.5} className="h-4 w-4 text-emerald-500" />
            </motion.div>
            
            {/* Headline with staggered reveal */}
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 60 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-7xl lg:text-8xl font-bold tracking-tight"
              >
                <span className="text-zinc-900">
                  {MARKETING_COPY.hero.headline[0]}
                </span>
              </motion.h1>
            </div>
            <div className="overflow-hidden">
              <motion.h1
                initial={{ opacity: 0, y: 60 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="text-5xl sm:text-7xl lg:text-8xl font-bold tracking-tight"
              >
                <span className="bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 bg-clip-text text-transparent">
                  {MARKETING_COPY.hero.headline[1]}
                </span>
              </motion.h1>
            </div>
            
            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="mt-8 text-lg sm:text-xl text-zinc-600 max-w-2xl mx-auto leading-relaxed"
            >
              {MARKETING_COPY.hero.subhead}
            </motion.p>
            
            {/* CTAs with hover effects */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1 }}
              className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <Link
                href="/get-started"
                className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800 hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Get Started Free</span>
                <ArrowRight strokeWidth={1.5} className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/features"
                className="group inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white/80 backdrop-blur-sm px-8 py-4 text-base font-semibold text-zinc-900 shadow-sm transition-all hover:bg-white hover:border-zinc-400 hover:scale-[1.02] active:scale-[0.98]"
              >
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Play strokeWidth={1.5} className="h-5 w-5 fill-zinc-900" />
                </motion.div>
                <span>See How It Works</span>
              </Link>
            </motion.div>
            
            {/* Live Metrics */}
            <LiveMetrics />
          </div>
          
          {/* Product Preview */}
          <motion.div
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1, duration: 0.8 }}
            className="mt-20 sm:mt-28"
          >
            <ProductPreview />
          </motion.div>
        </motion.div>
        
        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="flex flex-col items-center gap-2 text-zinc-400"
          >
            <span className="text-xs uppercase tracking-widest">Scroll</span>
            <div className="h-8 w-px bg-gradient-to-b from-zinc-400 to-transparent" />
          </motion.div>
        </motion.div>
      </section>

      {/* Logo Cloud - Light theme */}
      <section className="relative border-y border-zinc-200 bg-zinc-50 py-16">
        <div className="mx-auto max-w-7xl px-6">
          <motion.p 
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center text-sm text-zinc-500 mb-10"
          >
            Trusted by innovative teams worldwide
          </motion.p>
          <div className="flex flex-wrap items-center justify-center gap-x-16 gap-y-8">
            {["Acme Corp", "TechFlow", "DataSync", "CloudBase", "Quantum", "Nexus"].map((name, i) => (
              <motion.span
                key={name}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 0.4, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ opacity: 0.8 }}
                className="text-xl font-semibold text-zinc-500 transition-opacity cursor-default"
              >
                {name}
              </motion.span>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="relative py-32 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-12 sm:grid-cols-2 lg:grid-cols-4">
            {MARKETING_COPY.stats.map((stat) => (
              <AnimatedStat
                key={stat.label}
                value={stat.value}
                label={stat.label}
                suffix={"suffix" in stat ? stat.suffix : ""}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative py-32 bg-zinc-50">
        <FloatingOrb className="w-[500px] h-[500px] bg-emerald-100 top-1/4 -left-64" delay={1} />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              Built for operators, not chatbots
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              Connect, learn, execute, and measure — with approval gates and evidence at every step.
            </p>
          </motion.div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {MARKETING_COPY.homeFeatures.map((feature, i) => {
              const icons = [Bot, Users, Workflow, Shield, Zap, BarChart3]
              const Icon = icons[i] ?? Bot
              return (
                <FeatureCard
                  key={feature.title}
                  icon={Icon}
                  title={feature.title}
                  description={feature.description}
                  index={i}
                />
              )
            })}
          </div>
        </div>
      </section>

      <IntelligenceEngineSection />

      {/* Integrations Section - With real logos */}
      <section className="relative py-32 border-t border-zinc-200 bg-white">
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

      {/* Interactive Product Showcase - Chatbase style */}
      <section className="relative py-32 border-t border-zinc-200 overflow-hidden bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-emerald-50/30 to-transparent" />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 mb-6">
              <Play strokeWidth={1.5} className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">Discover the platform</span>
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              Powerful features, simple interface
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              See agents, workflows, runs, and learning surfaces in one interface.
            </p>
          </motion.div>

          <ProductShowcase />
        </div>
      </section>

      {/* How it Works - Interactive Chatbase-style */}
      <section className="relative py-32 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-20"
          >
            <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">{MARKETING_COPY.howItWorks.eyebrow}</span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              {MARKETING_COPY.howItWorks.title}
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              {MARKETING_COPY.howItWorks.subtitle}
            </p>
          </motion.div>

          <HowItWorks steps={[
            {
              number: MARKETING_COPY.howItWorks.steps[0].number,
              title: MARKETING_COPY.howItWorks.steps[0].title,
              description: MARKETING_COPY.howItWorks.steps[0].description,
              visual: (
                <div className="bg-zinc-900 rounded-xl p-6 shadow-2xl border border-zinc-800">
                  <div className="space-y-3">
                    {[
                      { label: "HubSpot", status: "Executable", ok: true },
                      { label: "Salesforce", status: "Auth required", ok: false },
                      { label: "Slack", status: "Healthy", ok: true },
                    ].map((row, i) => (
                      <motion.div
                        key={row.label}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 bg-zinc-800/50"
                      >
                        <span className="text-sm text-zinc-200">{row.label}</span>
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          row.ok ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                        }`}>{row.status}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              ),
            },
            {
              number: MARKETING_COPY.howItWorks.steps[1].number,
              title: MARKETING_COPY.howItWorks.steps[1].title,
              description: MARKETING_COPY.howItWorks.steps[1].description,
              visual: (
                <div className="bg-zinc-900 rounded-xl p-6 shadow-2xl border border-zinc-800">
                  <div className="space-y-3 text-sm">
                    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-3">
                      <p className="text-zinc-400 text-xs">Query clusters</p>
                      <p className="text-zinc-200 mt-1">47 distinct themes · 3 knowledge gaps detected</p>
                    </div>
                    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-3">
                      <p className="text-zinc-400 text-xs">Retrieval ranker</p>
                      <p className="text-zinc-200 mt-1">TRAINED · memory confidence 84%</p>
                    </div>
                  </div>
                </div>
              ),
            },
            {
              number: MARKETING_COPY.howItWorks.steps[2].number,
              title: MARKETING_COPY.howItWorks.steps[2].title,
              description: MARKETING_COPY.howItWorks.steps[2].description,
              visual: (
                <div className="bg-zinc-900 rounded-xl p-6 shadow-2xl border border-zinc-800">
                  <div className="flex items-center justify-center gap-2">
                    {[
                      { icon: Zap, color: "emerald" },
                      { icon: Bot, color: "blue" },
                      { icon: Users, color: "purple" },
                      { icon: Shield, color: "amber" },
                    ].map((node, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-center"
                      >
                        <div className={`h-12 w-12 rounded-xl flex items-center justify-center border ${
                          node.color === "emerald" ? "border-emerald-500/30 bg-emerald-500/10" :
                          node.color === "blue" ? "border-blue-500/30 bg-blue-500/10" :
                          node.color === "purple" ? "border-purple-500/30 bg-purple-500/10" : "border-amber-500/30 bg-amber-500/10"
                        }`}>
                          <node.icon className={`h-5 w-5 ${
                            node.color === "emerald" ? "text-emerald-400" :
                            node.color === "blue" ? "text-blue-400" :
                            node.color === "purple" ? "text-purple-400" : "text-amber-400"
                          }`} />
                        </div>
                        {i < 3 && <div className="w-6 h-0.5 bg-zinc-700" />}
                      </motion.div>
                    ))}
                  </div>
                </div>
              ),
            },
          ]} />
        </div>
      </section>

      {SHOW_MARKETING_TESTIMONIALS ? (
      <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center mb-16"
          >
            <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">Testimonials</span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-zinc-900">
              What people say
            </h2>
            <p className="mt-4 text-zinc-600">
              With over 10,000 clients served, here&apos;s what they have to say
            </p>
          </motion.div>

          <div className="max-w-3xl mx-auto">
            <TestimonialsCarousel testimonials={[
              {
                quote: "Gravitre is a strong signal of how enterprise automation will evolve. It is an early adopter of the agentic approach, which will become increasingly effective and trusted.",
                author: "Sarah Chen",
                role: "VP of Operations",
                company: "TechFlow Inc",
              },
              {
                quote: "The AI agents are intuitive, easy to configure, and have been effectively handling our workflows for nearly a year. The ROI has been incredible.",
                author: "Michael Torres",
                role: "CTO",
                company: "DataSync",
              },
              {
                quote: "Gravitre gave us a powerful, flexible way to launch our AI automation without the complexity we saw in other platforms. The team support is exceptional.",
                author: "Emily Watson",
                role: "Director of Engineering",
                company: "CloudBase",
              },
            ]} />
          </div>
        </div>
      </section>
      ) : null}

      {/* CTA Section */}
      <section className="relative py-32 bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-50 via-transparent to-transparent" />
        <FloatingOrb className="w-[600px] h-[600px] bg-emerald-100 -bottom-48 left-1/2 -translate-x-1/2" />
        
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="mx-auto max-w-3xl text-center"
          >
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-zinc-900">
              {MARKETING_COPY.cta.title}
            </h2>
            <p className="mt-6 text-lg text-zinc-600">
              {MARKETING_COPY.cta.subtitle}
            </p>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group relative inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800"
              >
                <span>Start Free Trial</span>
                <ArrowRight strokeWidth={1.5} className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-4 text-base font-semibold text-zinc-900 shadow-sm transition-all hover:bg-zinc-50"
              >
                Contact Sales
              </Link>
            </div>
            <p className="mt-6 text-sm text-zinc-500">
              Start your 7-day free trial today.
            </p>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
