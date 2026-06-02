import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Sign In — Gravitre AI Operations Platform",
  description: "Access your AI command center. Sign in with Google, GitHub, Microsoft, password, or magic link.",
  openGraph: {
    title: "Sign In — Gravitre AI Operations Platform",
    description: "Access your AI command center.",
    type: "website",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sign In — Gravitre AI Operations Platform",
    description: "Access your AI command center.",
    images: ["/og-get-started.png"],
  },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
