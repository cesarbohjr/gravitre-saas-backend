import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Welcome to Gravitre",
  description: "Set up your AI operations platform in a few guided steps.",
  robots: { index: false, follow: false },
}

export default function WelcomeLayout({ children }: { children: React.ReactNode }) {
  return children
}
