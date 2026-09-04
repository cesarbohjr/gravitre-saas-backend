"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Mail, MessageSquare, Phone, Check, Loader2, Building2, Headphones, Users } from "lucide-react"

const contactOptions = [
  { icon: Headphones, title: "Support", description: "Get help with your account or technical issues", action: "support@gravitre.app", href: "mailto:support@gravitre.app" },
  { icon: Building2, title: "Sales", description: "Learn about enterprise plans and custom solutions", action: "sales@gravitre.app", href: "mailto:sales@gravitre.app" },
  { icon: Users, title: "Partnerships", description: "Explore integration and partnership opportunities", action: "partners@gravitre.app", href: "mailto:partners@gravitre.app" },
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
    <div className="bg-card">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">Get in touch</h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">Have questions about Gravitre? We&apos;d love to hear from you. Send us a message and we&apos;ll respond as soon as possible.</p>
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
                <motion.a key={option.title} href={option.href} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-md">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-4 group-hover:bg-emerald-200 transition-colors">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-1">{option.title}</h3>
                  <p className="text-sm text-muted-foreground mb-3">{option.description}</p>
                  <span className="text-sm text-primary">{option.action}</span>
                </motion.a>
              )
            })}
          </div>
        </div>
      </section>

      {/* Contact Form */}
      <section className="px-6 py-24 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-12 lg:grid-cols-2">
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <h2 className="text-2xl font-semibold text-foreground mb-6">Send us a message</h2>
              
              {isSubmitted ? (
                <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="rounded-2xl border border-primary/20 bg-primary/10 p-8 text-center">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/15">
                    <Check className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">Message sent!</h3>
                  <p className="text-sm text-muted-foreground">Thanks for reaching out. We&apos;ll get back to you within 24 hours.</p>
                </motion.div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">Name</label>
                      <input type="text" value={formState.name} onChange={(e) => setFormState({ ...formState, name: e.target.value })} required className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" placeholder="Your name" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
                      <input type="email" value={formState.email} onChange={(e) => setFormState({ ...formState, email: e.target.value })} required className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" placeholder="you@company.com" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Company</label>
                    <input type="text" value={formState.company} onChange={(e) => setFormState({ ...formState, company: e.target.value })} className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" placeholder="Your company" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Subject</label>
                    <select value={formState.subject} onChange={(e) => setFormState({ ...formState, subject: e.target.value })} className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary">
                      <option value="general">General Inquiry</option>
                      <option value="sales">Sales & Pricing</option>
                      <option value="support">Technical Support</option>
                      <option value="partnership">Partnership</option>
                      <option value="press">Press & Media</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Message</label>
                    <textarea value={formState.message} onChange={(e) => setFormState({ ...formState, message: e.target.value })} required rows={5} className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary resize-none" placeholder="How can we help?" />
                  </div>
                  <button type="submit" disabled={isSubmitting} className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white transition-all hover:bg-primary/100 disabled:opacity-50">
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><span>Send message</span><ArrowRight className="h-4 w-4" /></>}
                  </button>
                </form>
              )}
            </motion.div>

            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} className="lg:pl-12">
              <h2 className="text-2xl font-semibold text-foreground mb-6">Other ways to reach us</h2>
              <div className="space-y-3">
                <a href="mailto:hello@gravitre.app" className="flex items-center gap-3 text-muted-foreground hover:text-foreground transition-colors"><Mail className="h-4 w-4" /><span className="text-sm">hello@gravitre.app</span></a>
                <a href="tel:+1-888-555-0123" className="flex items-center gap-3 text-muted-foreground hover:text-foreground transition-colors"><Phone className="h-4 w-4" /><span className="text-sm">+1 (888) 555-0123</span></a>
                <button onClick={() => window.open('https://gravitre.app/search', '_blank')} className="flex items-center gap-3 text-muted-foreground hover:text-foreground transition-colors"><MessageSquare className="h-4 w-4" /><span className="text-sm">Live chat (9am-6pm PT)</span></button>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* FAQ CTA */}
      <section className="px-6 py-24 border-t border-border">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h2 className="text-2xl font-semibold text-foreground mb-4">Looking for answers?</h2>
            <p className="text-muted-foreground mb-8">Check out our documentation and FAQ for quick answers to common questions.</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/docs" className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90">Browse docs<ArrowRight className="h-4 w-4" /></Link>
              <Link href="/support" className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted">Visit help center</Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
