import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Blog",
  description:
    "Product updates, engineering deep-dives, and best practices for running AI agents and workflows in production — from the Gravitre team.",
  openGraph: {
    title: "Blog · Gravitre",
    description: "Product updates, engineering deep-dives, and best practices for AI operations.",
  },
}

export default function BlogLayout({ children }: { children: React.ReactNode }) {
  return children
}
