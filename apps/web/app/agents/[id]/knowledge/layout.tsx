import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Agent knowledge | Gravitre",
  "Knowledge sources for this agent.",
  { canonical: "/agents" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
