import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Features",
  description:
    "Explore Gravitre's features: agent orchestration, workflow automation, run monitoring, approvals, governance, federation, and a marketplace of role-ready AI agents.",
  openGraph: {
    title: "Features · Gravitre",
    description:
      "Agent orchestration, workflow automation, run monitoring, approvals, governance, and a marketplace of role-ready AI agents.",
  },
}

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return children
}
