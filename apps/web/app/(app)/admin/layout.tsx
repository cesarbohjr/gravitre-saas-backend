import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Admin | Gravitre",
  "Administrative intelligence and org learning.",
  { canonical: "/admin" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
