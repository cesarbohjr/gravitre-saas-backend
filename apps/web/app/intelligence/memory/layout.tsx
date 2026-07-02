import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Organizational Memory | Gravitre Operator",
  description: "View and manage organizational memory, auto-promotions, and knowledge graph.",
}

export default function MemoryLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
