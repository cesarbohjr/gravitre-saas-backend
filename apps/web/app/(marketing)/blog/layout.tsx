import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Blog",
  description:
    "Product updates, engineering deep-dives, and best practices for running AI agents and workflows in production — from the Gravitre team.",
  ogDescription: "Product updates, engineering deep-dives, and best practices for AI operations.",
})

export default function BlogLayout({ children }: { children: React.ReactNode }) {
  return children
}
