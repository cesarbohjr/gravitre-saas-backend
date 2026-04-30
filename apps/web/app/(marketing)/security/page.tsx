"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  ArrowRight, 
  Shield, 
  Lock, 
  Eye, 
  Server,
  FileCheck,
  Users,
  Globe,
  CheckCircle2
} from "lucide-react"

const certifications = [
  { name: "GDPR Compliant", description: "Full compliance with EU data protection" },
  { name: "CCPA Compliant", description: "California consumer privacy rights" },
  { name: "AES-256 Encryption", description: "Industry-standard data encryption" },
  { name: "Role-based Access", description: "Fine-grained permission controls" },
]

const features = [
  {
    icon: Lock,
    title: "Encryption",
    description: "All data is encrypted at rest (AES-256) and in transit (TLS 1.3). We use industry-standard cryptographic protocols to protect your information.",
  },
  {
    icon: Shield,
    title: "Access Controls",
    description: "Role-based access control (RBAC), multi-factor authentication (MFA), and SSO/SAML support ensure only authorized users access your data.",
  },
  {
    icon: Eye,
    title: "Audit Logging",
    description: "Comprehensive audit logs track all user actions, API calls, and system events. Logs are retained and available for compliance review.",
  },
  {
    icon: Server,
    title: "Infrastructure",
    description: "Hosted on enterprise-grade cloud infrastructure with 99.9% uptime SLA. Multi-region deployment with automatic failover.",
  },
  {
    icon: FileCheck,
    title: "Vulnerability Management",
    description: "Regular penetration testing, automated vulnerability scanning, and a responsible disclosure program keep our systems secure.",
  },
  {
    icon: Users,
    title: "Security Team",
    description: "Dedicated security team monitoring 24/7. Incident response procedures tested quarterly with tabletop exercises.",
  },
]

const practices = [
  "End-to-end encryption for sensitive data",
  "Regular third-party security audits",
  "Automated threat detection and response",
  "Secure software development lifecycle (SDLC)",
  "Background checks for all employees",
  "Security awareness training",
  "Vendor security assessments",
  "Data backup and disaster recovery",
  "Network segmentation and firewalls",
  "Intrusion detection systems (IDS)",
]

export default function SecurityPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100">
              <Shield className="h-8 w-8 text-emerald-600" />
            </div>
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
              Enterprise-grade security
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Your data security is our top priority. Gravitre is built with security-first architecture 
              and maintains the highest compliance standards.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Certifications */}
      <section className="px-6 py-16 border-t border-zinc-200">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Certifications & Compliance</h2>
          </motion.div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {certifications.map((cert, i) => (
              <motion.div
                key={cert.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border border-zinc-200 bg-white p-4 text-center shadow-sm"
              >
                <div className="text-sm font-medium text-zinc-900 mb-1">{cert.name}</div>
                <div className="text-xs text-zinc-500">{cert.description}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Security Features */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Security Features</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              Comprehensive security controls built into every layer of our platform.
            </p>
          </motion.div>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => {
              const Icon = feature.icon
              return (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 mb-4">
                    <Icon className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-zinc-600">{feature.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Security Practices */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl">
          <div className="grid gap-12 lg:grid-cols-2 items-start">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <h2 className="text-3xl font-semibold text-zinc-900 mb-6">Our Security Practices</h2>
              <p className="text-zinc-600 mb-6">
                We implement comprehensive security practices across our organization, from secure 
                development to operational security.
              </p>
              <Link
                href="/docs/security"
                className="inline-flex items-center gap-2 text-emerald-600 hover:text-emerald-500 transition-colors"
              >
                View security documentation
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <ul className="space-y-3">
                {practices.map((practice, i) => (
                  <motion.li
                    key={practice}
                    initial={{ opacity: 0, x: 10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-center gap-3"
                  >
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    <span className="text-sm text-zinc-700">{practice}</span>
                  </motion.li>
                ))}
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Data Centers */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <Globe className="h-8 w-8 text-emerald-600 mx-auto mb-4" />
            <h2 className="text-3xl font-semibold text-zinc-900 mb-4">Global Infrastructure</h2>
            <p className="text-zinc-600 max-w-2xl mx-auto">
              Your data is hosted in enterprise-grade data centers with geographic redundancy 
              and data residency options.
            </p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-3">
            {[
              { region: "North America", locations: "US-East, US-West" },
              { region: "Europe", locations: "Frankfurt, London" },
              { region: "Asia Pacific", locations: "Singapore, Sydney" },
            ].map((region, i) => (
              <motion.div
                key={region.region}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border border-zinc-200 bg-white p-5 text-center shadow-sm"
              >
                <div className="font-medium text-zinc-900 mb-1">{region.region}</div>
                <div className="text-sm text-zinc-500">{region.locations}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Report Vulnerability */}
      <section className="px-6 py-24 border-t border-zinc-200">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Report a Security Vulnerability</h2>
            <p className="text-zinc-600 mb-8 max-w-xl mx-auto">
              We take security seriously. If you&apos;ve discovered a vulnerability, please report it responsibly.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="mailto:security@gravitre.com"
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
              >
                security@gravitre.com
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                href="/security/bug-bounty"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100"
              >
                Bug bounty program
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Trust Center CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-zinc-200 bg-white p-8 lg:p-12 text-center shadow-sm"
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Need more details?</h2>
            <p className="text-zinc-600 mb-8">
              Request access to our Trust Center for detailed security documentation, 
              audit reports, and compliance certifications.
            </p>
            <Link
              href="/contact?subject=trust-center"
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-500"
            >
              Request access
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
