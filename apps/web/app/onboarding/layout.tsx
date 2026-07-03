import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Welcome | Gravitre",
  "Complete your Gravitre workspace setup.",
  { canonical: "/welcome" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
