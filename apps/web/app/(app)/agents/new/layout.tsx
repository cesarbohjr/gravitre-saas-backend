import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "New agent | Gravitre",
  "Create a new AI agent.",
  { canonical: "/agents/new" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
