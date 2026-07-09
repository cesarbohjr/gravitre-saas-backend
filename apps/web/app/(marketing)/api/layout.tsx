import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "API",
  description:
    "Build with the Gravitre REST API — execute workflows, query intelligence endpoints, manage connectors, and wire approval gates into your stack.",
  ogDescription: "REST API reference, quickstart, webhooks, and authentication for Gravitre.",
})

export default function ApiLayout({ children }: { children: React.ReactNode }) {
  return children
}
