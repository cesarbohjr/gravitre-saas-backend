import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Sources | Gravitre",
  "Knowledge sources and document ingestion.",
  { canonical: "/sources" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
