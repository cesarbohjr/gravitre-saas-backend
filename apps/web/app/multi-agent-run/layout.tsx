import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Multi-Agent Run | Gravitre",
  description:
    "Coordinate multiple AI agents on parallel subtasks and merge their results into one recommendation.",
  alternates: { canonical: "/multi-agent-run" },
}

export default function MultiAgentRunLayout({ children }: { children: React.ReactNode }) {
  return children
}
