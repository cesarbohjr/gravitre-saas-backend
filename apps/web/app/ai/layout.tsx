import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Gravitre AI | Gravitre",
  "Unified AI surface for execute, chat, and search.",
  { canonical: "/ai" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
