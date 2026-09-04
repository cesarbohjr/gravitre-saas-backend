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
  { name: "Encryption in transit and at rest", description: "TLS for data in motion; AES-256 at rest on eligible infrastructure" },
  { name: "Role-based access", description: "RBAC, MFA, and SSO/SAML on eligible plans" },
  { name: "Audit logging", description: "Connector writes and approvals logged for operator review" },
  { name: "Responsible disclosure", description: "Security issues reported through our disclosure process" },
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
    description: "Audit trails show connector writes and approvals so operators can see what the AI did — and what it asked before acting. Logs are retained for compliance review.",
  },
  {
    icon: Server,
    title: "Infrastructure",
    description:
      "Hosted on enterprise-grade cloud infrastructure. Availability targets and failover posture depend on your plan and contract — ask us for specifics.",
  },
  {
    icon: FileCheck,
    title: "Vulnerability management",
    description:
      "Regular security testing and automated scanning. We maintain a responsible disclosure program for reported issues.",
  },
  {
    icon: Users,
    title: "Security practices",
    description:
      "Documented incident response procedures and security-aware engineering practices. Enterprise support options vary by plan.",
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
    <div className="bg-card">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/15">
              <Shield className="h-8 w-8 text-primary" />
            </div>
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Enterprise-grade security
            </h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
              Your data security is our priority. Gravitre is built with security-first architecture,
              human approval on writes, and audit trails you can review — with plan-specific details available on request.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Certifications */}
      <section className="px-6 py-16 border-t border-border">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-semibold text-foreground mb-4">Security controls</h2>
          </motion.div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {certifications.map((cert, i) => (
              <motion.div
                key={cert.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border border-border bg-card p-4 text-center shadow-sm"
              >
                <div className="text-sm font-medium text-foreground mb-1">{cert.name}</div>
                <div className="text-xs text-muted-foreground">{cert.description}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Security Features */}
      <section className="px-6 py-24 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-semibold text-foreground mb-4">Security Features</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
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
                  className="rounded-2xl border border-border bg-card p-6 shadow-sm"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-4">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Security Practices */}
      <section className="px-6 py-24 border-t border-border">
        <div className="mx-auto max-w-4xl">
          <div className="grid gap-12 lg:grid-cols-2 items-start">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <h2 className="text-3xl font-semibold text-foreground mb-6">Our Security Practices</h2>
              <p className="text-muted-foreground mb-6">
                We implement comprehensive security practices across our organization, from secure 
                development to operational security.
              </p>
              <Link
                href="/docs/security"
                className="inline-flex items-center gap-2 text-primary hover:text-primary transition-colors"
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
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />
                    <span className="text-sm text-foreground">{practice}</span>
                  </motion.li>
                ))}
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Data Centers */}
      <section className="px-6 py-24 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <Globe className="h-8 w-8 text-primary mx-auto mb-4" />
            <h2 className="text-3xl font-semibold text-foreground mb-4">Data residency</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Hosting regions and data residency options depend on your plan and contract. Contact us for
              current availability — we do not publish specific region lists without confirming your deployment.
            </p>
          </motion.div>
          <div className="mx-auto max-w-xl rounded-xl border border-border bg-card p-6 text-center shadow-sm">
            <p className="text-sm text-muted-foreground">
              Enterprise customers can request deployment details, subprocessors, and DPA terms through our Trust Center.
            </p>
            <Link
              href="/contact?subject=trust-center"
              className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary"
            >
              Request Trust Center access
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Report Vulnerability */}
      <section className="px-6 py-24 border-t border-border">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-foreground mb-4">Report a Security Vulnerability</h2>
            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
              We take security seriously. If you&apos;ve discovered a vulnerability, please report it responsibly.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="mailto:security@gravitre.app"
                className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90"
              >
                security@gravitre.app
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                href="/contact?subject=bug-bounty"
                className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted"
              >
                Bug bounty program
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Trust Center CTA */}
      <section className="px-6 py-24 border-t border-border bg-muted/50">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-border bg-card p-8 lg:p-12 text-center shadow-sm"
          >
            <h2 className="text-2xl font-semibold text-foreground mb-4">Need more details?</h2>
            <p className="text-muted-foreground mb-8">
              Request access to our Trust Center for detailed security documentation, 
              audit reports, and compliance certifications.
            </p>
            <Link
              href="/contact?subject=trust-center"
              className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-white transition-all hover:bg-primary/100"
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
