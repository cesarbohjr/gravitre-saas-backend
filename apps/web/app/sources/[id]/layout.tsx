import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Source | Gravitre",
  "Knowledge source schema and sync.",
  { canonical: "/sources" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
