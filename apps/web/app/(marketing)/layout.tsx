import type { Metadata } from "next"
import { MarketingChrome } from "@/components/marketing/marketing-chrome"

export const metadata: Metadata = {
  title: {
    default: "Gravitre — Your AI Team, Managed Simply",
    template: "%s · Gravitre",
  },
  description:
    "Gravitre is the AI operations platform for managing agents, workflows, runs, and approvals — with enterprise-grade governance, federation, and a marketplace of role-ready agents.",
  keywords: [
    "AI operations",
    "AI agents",
    "agent workflows",
    "AI governance",
    "AI orchestration",
    "enterprise AI platform",
  ],
  openGraph: {
    type: "website",
    siteName: "Gravitre",
    title: "Gravitre — Your AI Team, Managed Simply",
    description:
      "Manage AI agents, workflows, runs, and approvals with enterprise-grade governance and a marketplace of role-ready agents.",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — AI Operations Platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Gravitre — Your AI Team, Managed Simply",
    description:
      "Manage AI agents, workflows, runs, and approvals with enterprise-grade governance and a marketplace of role-ready agents.",
    images: ["/og-get-started.png"],
  },
}

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return <MarketingChrome>{children}</MarketingChrome>
}
