import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "About",
  description:
    "Gravitre's mission is to make AI teams as manageable as human ones. Learn about the company building the AI operations platform for the enterprise.",
  openGraph: {
    title: "About · Gravitre",
    description: "The company building the AI operations platform for the enterprise.",
  },
}

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return children
}
