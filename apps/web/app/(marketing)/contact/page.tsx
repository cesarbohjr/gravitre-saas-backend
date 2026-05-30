"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Mail, MapPin, MessageSquare, Phone, Check, Loader2, Building2, Headphones, Users } from "lucide-react"

const contactOptions = [
  { icon: Headphones, title: "Support", description: "Get help with your account or technical issues", action: "support@gravitre.com", href: "mailto:support@gravitre.com" },
  { icon: Building2, title: "Sales", description: "Learn about enterprise plans and custom solutions", action: "sales@gravitre.com", href: "mailto:sales@gravitre.com" },
  { icon: Users, title: "Partnerships", description: "Explore integration and partnership opportunities", action: "partners@gravitre.com", href: "mailto:partners@gravitre.com" },
]

const offices = [
  { city: "San Francisco", address: "548 Market St, Suite 35000", country: "United States" },
  { city: "London", address: "30 Fenchurch Street", country: "United Kingdom" },
  { city: "Singapore", address: "Marina Bay Sands Tower 1", country: "Singapore" },
]

export default function ContactPage() {
  const [formState, setFormState] = useState({ name: "", email: "", company: "", subject: "general", message: "" })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    setIsSubmitting(false)
    setIsSubmitted(true)
  }

  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">Get in touch</h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">Have questions about Gravitre? We&apos;d love to hear from you. Send us a message and we&apos;ll respond as soon as possible.</p>
          </motion.div>
        </div>
      </section>

      {/* Contact Options */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-6 md:grid-cols-3">
            {contactOptions.map((option, i) => {
              const Icon = option.icon
              return (
                <motion.a key={option.title} href={option.href} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="group rounded-2xl border border-zinc-200 bg-white p-6 transition-all hover:border-emerald-300 hover:shadow-md">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 mb-4 group-hover:bg-emerald-200 transition-colors">
                    <Icon className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-900 mb-1">{option.title}</h3>
                  <p className="text-sm text-zinc-500 mb-3">{option.description}</p>
                  <span className="text-sm text-emerald-600">{option.action}</span>
                </motion.a>
              )
            })}
          </div>
        </div>
      </section>

      {/* Contact Form */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-12 lg:grid-cols-2">
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <h2 className="text-2xl font-semibold text-zinc-900 mb-6">Send us a message</h2>
              
              {isSubmitted ? (
                <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100">
                    <Check className="h-6 w-6 text-emerald-600" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-900 mb-2">Message sent!</h3>
                  <p className="text-sm text-zinc-600">Thanks for reaching out. We&apos;ll get back to you within 24 hours.</p>
                </motion.div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">Name</label>
                      <input type="text" value={formState.name} onChange={(e) => setFormState({ ...formState, name: e.target.value })} required className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500" placeholder="Your name" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">Email</label>
                      <input type="email" value={formState.email} onChange={(e) => setFormState({ ...formState, email: e.target.value })} required className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500" placeholder="you@company.com" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Company</label>
                    <input type="text" value={formState.company} onChange={(e) => setFormState({ ...formState, company: e.target.value })} className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500" placeholder="Your company" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Subject</label>
                    <select value={formState.subject} onChange={(e) => setFormState({ ...formState, subject: e.target.value })} className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500">
                      <option value="general">General Inquiry</option>
                      <option value="sales">Sales & Pricing</option>
                      <option value="support">Technical Support</option>
                      <option value="partnership">Partnership</option>
                      <option value="press">Press & Media</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Message</label>
                    <textarea value={formState.message} onChange={(e) => setFormState({ ...formState, message: e.target.value })} required rows={5} className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 resize-none" placeholder="How can we help?" />
                  </div>
                  <button type="submit" disabled={isSubmitting} className="w-full flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-500 disabled:opacity-50">
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><span>Send message</span><ArrowRight className="h-4 w-4" /></>}
                  </button>
                </form>
              )}
            </motion.div>

            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} className="lg:pl-12">
              <h2 className="text-2xl font-semibold text-zinc-900 mb-6">Our Offices</h2>
              <div className="space-y-6">
                {offices.map((office) => (
                  <div key={office.city} className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white border border-zinc-200 shadow-sm">
                      <MapPin className="h-4 w-4 text-zinc-500" />
                    </div>
                    <div>
                      <h3 className="font-medium text-zinc-900">{office.city}</h3>
                      <p className="text-sm text-zinc-500">{office.address}</p>
                      <p className="text-sm text-zinc-500">{office.country}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-12 pt-12 border-t border-zinc-200">
                <h3 className="font-medium text-zinc-900 mb-4">Other ways to reach us</h3>
                <div className="space-y-3">
                  <a href="mailto:hello@gravitre.com" className="flex items-center gap-3 text-zinc-600 hover:text-zinc-900 transition-colors"><Mail className="h-4 w-4" /><span className="text-sm">hello@gravitre.com</span></a>
                  <a href="tel:+1-888-555-0123" className="flex items-center gap-3 text-zinc-600 hover:text-zinc-900 transition-colors"><Phone className="h-4 w-4" /><span className="text-sm">+1 (888) 555-0123</span></a>
                  <button onClick={() => window.open('https://gravitre.com/chat', '_blank')} className="flex items-center gap-3 text-zinc-600 hover:text-zinc-900 transition-colors"><MessageSquare className="h-4 w-4" /><span className="text-sm">Live chat (9am-6pm PT)</span></button>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* FAQ CTA */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Looking for answers?</h2>
            <p className="text-zinc-600 mb-8">Check out our documentation and FAQ for quick answers to common questions.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/docs" className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800">Browse docs<ArrowRight className="h-4 w-4" /></Link>
              <Link href="/support" className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">Visit help center</Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
