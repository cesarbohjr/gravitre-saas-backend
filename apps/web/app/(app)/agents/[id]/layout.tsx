import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Agent profile | Gravitre",
  "Agent capabilities, memory, and performance.",
  { canonical: "/agents" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
