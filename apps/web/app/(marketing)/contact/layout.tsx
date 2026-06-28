import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Get in touch with the Gravitre team. Talk to sales, request a demo, or ask about enterprise deployment, security, and federation.",
  openGraph: {
    title: "Contact · Gravitre",
    description: "Talk to sales, request a demo, or ask about enterprise deployment.",
  },
}

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children
}
