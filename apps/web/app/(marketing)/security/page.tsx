"use client"

import Link from "next/link"
import { Lock, Server, FileCheck, Users } from "lucide-react"
import {
  NucleoApproval,
  NucleoActivity,
  NucleoArrowRight,
} from "@/components/icons/nucleo/semantic"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageHero,
  MarketingRails,
  MarketingPageEndCta,
} from "@/components/marketing/nodus/page-shell"
import {
  GravitreFlow,
  GravitreReveal,
  GravitreResolve,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
  SECURITY_TRACE_STAGES,
} from "@/components/marketing/system"

const controls = [
  {
    name: "Encryption in transit and at rest",
    description: "TLS for data in motion; AES-256 at rest on eligible infrastructure",
  },
  {
    name: "Role-based access",
    description: "RBAC, MFA, and SSO/SAML on eligible plans",
  },
  {
    name: "Audit logging",
    description: "Connector writes and approvals logged for operator review",
  },
  {
    name: "Responsible disclosure",
    description: "Security issues reported through our disclosure process",
  },
]

const features = [
  {
    icon: Lock,
    title: "Encryption",
    description:
      "All data is encrypted at rest (AES-256) and in transit (TLS 1.3). We use industry-standard cryptographic protocols to protect your information.",
  },
  {
    icon: NucleoApproval,
    title: "Access Controls",
    description:
      "Role-based access control (RBAC), multi-factor authentication (MFA), and SSO/SAML support ensure only authorized users access your data — plan-specific; ask us for details.",
  },
  {
    icon: NucleoActivity,
    title: "Audit Logging",
    description:
      "Audit trails show connector writes and approvals so operators can see what the AI did — and what it asked before acting. Retention is plan-specific.",
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
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Security"
        title="Enterprise-grade security"
        description="Your data security is our priority. Gravitre is built with security-first architecture, human approval on writes, and audit trails you can review — with plan-specific details available on request."
      />

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Governance path"
          title="Identity → Encrypt → Approve → Audit"
          description="One signature TRACE — how access and writes move through Gravitre before anything lands in your systems."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={SECURITY_TRACE_STAGES}
            gradientId="security-trace"
            ariaLabel="Security path from identity through encrypt and approve to audit"
            caption="Identity → encrypt → approve → audit — plan-specific controls; ask us for the details that match your contract."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <div className="mb-16">
          <GravitreReveal className="mb-12 text-center">
            <h2 className="mb-4 text-2xl font-semibold text-foreground">Security controls</h2>
          </GravitreReveal>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {controls.map((cert, i) => (
              <GravitreFlow
                key={cert.name}
                delay={i * 0.08}
                className="rounded-xl border border-divide bg-gray-50 p-4 text-center"
              >
                <div className="mb-1 text-sm font-medium text-foreground">{cert.name}</div>
                <div className="text-xs text-muted-foreground">{cert.description}</div>
              </GravitreFlow>
            ))}
          </div>
        </div>

        <div className="mb-16">
          <GravitreReveal className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-semibold text-foreground">Security Features</h2>
            <p className="mx-auto max-w-2xl text-muted-foreground">
              Security controls built into every layer of our platform — specifics vary by plan.
            </p>
          </GravitreReveal>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => {
              const Icon = feature.icon
              return (
                <GravitreFlow
                  key={feature.title}
                  delay={i * 0.08}
                  className="rounded-xl border border-divide bg-gray-50 p-6"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="mb-2 text-lg font-medium text-foreground">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                </GravitreFlow>
              )
            })}
          </div>
        </div>

        <div className="grid items-start gap-12 lg:grid-cols-2">
          <GravitreFlow>
            <h2 className="mb-6 text-3xl font-semibold text-foreground">Our Security Practices</h2>
            <p className="mb-6 text-gray-600">
              We implement security practices across our organization, from secure development to
              operational security. Ask us for plan-specific details.
            </p>
            <Link
              href="/docs/security"
              className="inline-flex items-center gap-2 text-primary transition-colors hover:text-primary"
            >
              View security documentation
              <NucleoArrowRight className="h-4 w-4" />
            </Link>
          </GravitreFlow>
          <GravitreResolve>
            <ul className="space-y-3">
              {practices.map((practice, i) => (
                <GravitreFlow key={practice} delay={i * 0.04} className="flex items-center gap-3">
                  <NucleoApproval className="h-4 w-4 shrink-0 text-primary" />
                  <span className="text-sm text-foreground">{practice}</span>
                </GravitreFlow>
              ))}
            </ul>
          </GravitreResolve>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
