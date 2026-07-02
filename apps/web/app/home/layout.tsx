import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Home | Gravitre",
  description: "Your role-aware Gravitre home — quick actions, intelligence health, and pending approvals.",
  robots: { index: false, follow: false },
}

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return children
}
