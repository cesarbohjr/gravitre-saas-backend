import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "About",
  description:
    "Gravitre's mission is to make AI teams as manageable as human ones. Learn about the company building the AI operations platform for the enterprise.",
  ogDescription: "The company building the AI operations platform for the enterprise.",
})

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return children
}
