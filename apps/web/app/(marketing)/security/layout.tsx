import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Security",
  description:
    "How Gravitre protects your data: encryption, access controls, audit logging, compliance, and enterprise-grade governance for AI operations.",
  openGraph: {
    title: "Security · Gravitre",
    description: "Encryption, access controls, audit logging, and compliance for AI operations.",
  },
}

export default function SecurityLayout({ children }: { children: React.ReactNode }) {
  return children
}
