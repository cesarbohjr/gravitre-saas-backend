import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Agent chat | Gravitre",
  "Chat with a dedicated agent.",
  { canonical: "/agents" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
