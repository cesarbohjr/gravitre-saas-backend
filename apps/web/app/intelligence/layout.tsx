import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Intelligence Center | Gravitre",
  description:
    "See what Gravitre knows, why recommendations were made, and how agents and models perform.",
}

export default function IntelligenceLayout({ children }: { children: React.ReactNode }) {
  return children
}
