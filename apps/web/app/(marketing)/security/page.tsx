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
import { MarketingPageHero, MarketingRails, MarketingPageEndCta } from "@/components/marketing/nodus/page-shell"

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
    <div className="bg-white">
      <MarketingPageHero
        badge="Security"
        title="Enterprise-grade security"
        description="Your data security is our priority. Gravitre is built with security-first architecture, human approval on writes, and audit trails you can review — with plan-specific details available on request."
      />

      <MarketingRails>
        {/* Certifications */}
        <div className="mb-16">
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
                className="rounded-xl border border-border bg-gray-50 p-4 text-center"
              >
                <div className="text-sm font-medium text-foreground mb-1">{cert.name}</div>
                <div className="text-xs text-muted-foreground">{cert.description}</div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Security Features */}
        <div className="mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-semibold text-foreground mb-4">Security Features</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Comprehensive security controls built into every layer of our platform.
            </p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => {
              const Icon = feature.icon
              return (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="rounded-xl border border-border bg-gray-50 p-6"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-4">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>

        {/* Security Practices */}
        <div className="grid gap-12 lg:grid-cols-2 items-start">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-semibold text-foreground mb-6">Our Security Practices</h2>
            <p className="text-gray-600 mb-6">
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
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
