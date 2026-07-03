import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Deliverables | Gravitre",
  "Goal deliverables and outputs from agent work.",
  { canonical: "/deliverables" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
