import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Command Center | Gravitre",
  "Delegate tasks and track async operator work.",
  { canonical: "/ai" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
