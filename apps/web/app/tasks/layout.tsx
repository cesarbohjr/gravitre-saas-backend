import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Tasks | Gravitre",
  "Task queue and assignment tracking.",
  { canonical: "/tasks" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
