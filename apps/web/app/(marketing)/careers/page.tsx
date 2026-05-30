"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, MapPin, Clock, Users, Zap, Heart, Globe } from "lucide-react"

const benefits = [
  { icon: Heart, title: "Health & Wellness", description: "Comprehensive health, dental, and vision insurance for you and your family" },
  { icon: Zap, title: "Equity", description: "Competitive equity packages so you share in our success" },
  { icon: Globe, title: "Remote-first", description: "Work from anywhere with flexible hours and async communication" },
  { icon: Users, title: "Learning & Growth", description: "$2,500 annual learning budget for courses, conferences, and books" },
  { icon: Clock, title: "Unlimited PTO", description: "Take the time you need to recharge and do your best work" },
  { icon: MapPin, title: "Offsites", description: "Regular team retreats to connect in person and have fun together" },
]

const departments = ["Engineering", "Product", "Design", "Sales", "Marketing", "Operations"]

const jobs = [
  { id: 1, title: "Senior Software Engineer, Platform", department: "Engineering", location: "Remote (US)", type: "Full-time" },
  { id: 2, title: "Staff Machine Learning Engineer", department: "Engineering", location: "San Francisco / Remote", type: "Full-time" },
  { id: 3, title: "Senior Product Designer", department: "Design", location: "Remote (US/EU)", type: "Full-time" },
  { id: 4, title: "Product Manager, AI Operator", department: "Product", location: "San Francisco", type: "Full-time" },
  { id: 5, title: "Account Executive, Enterprise", department: "Sales", location: "New York / Remote", type: "Full-time" },
  { id: 6, title: "Senior DevOps Engineer", department: "Engineering", location: "Remote", type: "Full-time" },
  { id: 7, title: "Content Marketing Manager", department: "Marketing", location: "Remote (US)", type: "Full-time" },
  { id: 8, title: "Solutions Engineer", department: "Sales", location: "San Francisco / London", type: "Full-time" },
]

export default function CareersPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 mb-6">
              We&apos;re hiring
            </span>
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl text-balance">
              Build the future of AI operations with us
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Join a world-class team working on challenging problems at the intersection of AI, automation, and enterprise software.
            </p>
            <div className="mt-8">
              <a href="#openings" className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800">
                View open roles
                <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-8 sm:grid-cols-4 text-center">
            {[
              { value: "80+", label: "Team members" },
              { value: "15+", label: "Countries" },
              { value: "4.8", label: "Glassdoor rating" },
              { value: "$105M", label: "Total funding" },
            ].map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}>
                <div className="text-3xl font-semibold text-zinc-900">{stat.value}</div>
                <div className="text-sm text-zinc-500 mt-1">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Why Join */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-16">
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Why join Gravitre?</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">We offer competitive compensation and benefits, plus a culture that values impact over hours.</p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {benefits.map((benefit, i) => {
              const Icon = benefit.icon
              return (
                <motion.div key={benefit.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 mb-4">
                    <Icon className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-900 mb-2">{benefit.title}</h3>
                  <p className="text-sm text-zinc-600">{benefit.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Open Roles */}
      <section id="openings" className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-12">
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Open roles</h2>
            <p className="text-zinc-600">
              Don&apos;t see a role that fits? Send us your resume at <a href="mailto:careers@gravitre.com" className="text-emerald-600 hover:text-emerald-500">careers@gravitre.com</a>
            </p>
          </motion.div>

          <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
            <button className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white">All</button>
            {departments.map((dept) => (
              <button key={dept} className="rounded-full border border-zinc-200 px-4 py-1.5 text-sm text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors">{dept}</button>
            ))}
          </div>

          <div className="space-y-3">
            {jobs.map((job, i) => (
              <motion.a key={job.id} href={`/careers/${job.id}`} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }} className="group flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-5 transition-all hover:border-emerald-300 hover:shadow-md">
                <div>
                  <h3 className="font-medium text-zinc-900 group-hover:text-emerald-700 transition-colors">{job.title}</h3>
                  <div className="flex items-center gap-4 mt-1">
                    <span className="text-sm text-zinc-500">{job.department}</span>
                    <span className="text-sm text-zinc-500 flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>
                    <span className="text-sm text-zinc-500">{job.type}</span>
                  </div>
                </div>
                <ArrowRight className="h-5 w-5 text-zinc-400 group-hover:text-emerald-600 transition-colors" />
              </motion.a>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Not ready to apply?</h2>
            <p className="text-zinc-600 mb-8">Follow us on social media and our blog to stay updated on new roles and company news.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/blog" className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">Read our blog</Link>
              <a href="https://twitter.com" className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">Follow on X</a>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
