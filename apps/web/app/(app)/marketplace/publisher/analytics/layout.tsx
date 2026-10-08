import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Publisher analytics | Gravitre",
  "Publisher revenue and installs.",
  { canonical: "/marketplace/publisher/analytics" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
