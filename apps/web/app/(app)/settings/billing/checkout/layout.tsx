import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Checkout | Gravitre",
  "Complete your billing checkout.",
  { canonical: "/settings/billing/checkout" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
