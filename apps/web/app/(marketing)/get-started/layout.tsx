import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Get Started Free — Gravitre AI Operations Platform",
  description: "Build your AI team in minutes. Agents that work like employees, integrations they use as tools, workflows that run the business. No credit card required.",
  openGraph: {
    title: "Get Started Free — Gravitre AI Operations Platform",
    description: "Build your AI team in minutes. No credit card required.",
    type: "website",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — Get started free" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Get Started Free — Gravitre AI Operations Platform",
    description: "Build your AI team in minutes. No credit card required.",
    images: ["/og-get-started.png"],
  },
}

export default function GetStartedLayout({ children }: { children: React.ReactNode }) {
  return children
}
