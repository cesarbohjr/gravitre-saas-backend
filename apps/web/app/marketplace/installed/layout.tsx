import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Installed assets | Gravitre",
  "Assets deployed in your org.",
  { canonical: "/marketplace/installed" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
