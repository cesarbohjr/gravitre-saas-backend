import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Get Started Free — Gravitre",
  description:
    "Put one AI brain to work. Connect your stack, run agents and workflows, approve what matters. No credit card required.",
  openGraph: {
    title: "Get Started Free — Gravitre",
    description: "Connect your stack. Run governed AI work. Start free.",
    type: "website",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — Get started free" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Get Started Free — Gravitre",
    description: "Connect your stack. Run governed AI work. Start free.",
    images: ["/og-get-started.png"],
  },
}

export default function GetStartedLayout({ children }: { children: React.ReactNode }) {
  return children
}
