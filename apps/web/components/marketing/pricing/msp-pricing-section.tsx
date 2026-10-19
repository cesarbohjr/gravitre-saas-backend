import Link from "next/link"
import { Building2, HandCoins, Palette, Receipt } from "lucide-react"
import { Container } from "@/components/marketing/nodus/container"
import { Badge } from "@/components/marketing/nodus/badge"
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading"
import { Button } from "@/components/marketing/nodus/button"
import { MSP_DOCS_HREF, MSP_EARNING_COPY } from "@/lib/msp-program-copy"

/**
 * /pricing#msp — the partner program for MSPs and agencies.
 * No wholesale dollar figures here: partners see the exact wholesale price per
 * plan in Settings › Clients before they add a client.
 */
export function MspPricingSection() {
  const points = [
    {
      icon: HandCoins,
      title: "Wholesale price, your price",
      body: "Gravitre charges you a wholesale price for each client workspace, below the list price. You decide what the client pays.",
    },
    {
      icon: Receipt,
      title: "One bill for all clients",
      body: "A single subscription covers every client. Adding, removing or changing a client's plan is prorated automatically.",
    },
    {
      icon: Palette,
      title: "Your brand",
      body: "Client workspaces use your white label unless they set their own, so the AI layer looks like your service.",
    },
    {
      icon: Building2,
      title: "Client consent",
      body: "Clients approve the link and choose what your team can see: full access, or account health only. They can detach any time.",
    },
  ]
  const steps = [
    { step: "01", title: "Join", body: "Open Settings › Clients in your own workspace and join the partner program." },
    { step: "02", title: "Add clients", body: "Create a workspace for a client, or link one they already have." },
    { step: "03", title: "Start billing", body: "Start one wholesale subscription with your first client." },
    { step: "04", title: "Rebill", body: "Set your price per client and download a monthly statement to invoice from." },
  ]
  return (
    <Container id="msp" className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <Badge text="For MSPs" />
        <SectionHeading className="mt-4">Resell Gravitre to your clients</SectionHeading>
        <p className="mt-3 text-base text-gray-600">{MSP_EARNING_COPY}</p>
      </div>
      <div className="divide-divide mt-10 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
        {points.map((point) => (
          <div key={point.title} className="p-4 md:p-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand/10 text-brand">
              <point.icon className="h-4 w-4" />
            </div>
            <p className="text-charcoal-700 mt-3 font-medium">{point.title}</p>
            <p className="mt-2 text-sm text-gray-600">{point.body}</p>
          </div>
        ))}
      </div>
      <div className="border-divide mt-10 border-t pt-10">
        <h3 className="text-charcoal-700 text-center text-lg font-medium">How to start</h3>
        <ol className="divide-divide mt-6 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
          {steps.map((item) => (
            <li key={item.step} className="p-4 md:p-6">
              <span className="font-mono text-xs text-gray-500">{item.step}</span>
              <p className="text-charcoal-700 mt-1 font-medium">{item.title}</p>
              <p className="mt-2 text-sm text-gray-600">{item.body}</p>
            </li>
          ))}
        </ol>
        <p className="mx-auto mt-6 max-w-2xl text-center text-sm text-gray-500">
          The exact wholesale price for each plan is shown in Settings › Clients before you add a client. Clients
          on your bill never receive a Gravitre invoice.
        </p>
        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button as={Link} href="/get-started" variant="primary">
            Start as a partner
          </Button>
          <Button as={Link} href={MSP_DOCS_HREF} variant="secondary">
            Read the partner guide
          </Button>
        </div>
      </div>
    </Container>
  )
}
