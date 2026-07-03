import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Systems | Gravitre",
  "Connected systems overview.",
  { canonical: "/systems" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
