import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Contact",
  description:
    "Get in touch with the Gravitre team. Talk to sales, request a demo, or ask about enterprise deployment, security, and federation.",
  ogDescription: "Talk to sales, request a demo, or ask about enterprise deployment.",
})

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children
}
