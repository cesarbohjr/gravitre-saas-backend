import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Assignments | Gravitre",
  "Assign work to AI agents and track deliverables.",
  { canonical: "/assignments" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
