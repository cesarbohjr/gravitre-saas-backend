import React from "react"
import { Container } from "./container"
import { Heading } from "./heading"
import { SubHeading } from "./subheading"
import { Button } from "./button"
import Link from "next/link"
import { MARKETING_COPY } from "@/lib/marketing-copy"

/**
 * Nodus hero layout · Gravitre copy · green brand accent.
 * Gartner / unverified social proof intentionally omitted.
 *
 * Server component: static badge (no ShimmerText / framer-motion above the fold).
 */
export const Hero = () => {
  const h = MARKETING_COPY.hero
  return (
    <Container className="border-divide flex flex-col items-center justify-center border-x px-4 pt-10 pb-10 md:pt-32 md:pb-20">
      <span className="text-sm font-normal text-brand">One AI brain for your entire business</span>
      <Heading className="mt-4 max-w-full px-1 text-balance">
        Manage agents, workflows, and{" "}
        <span className="text-brand">operations</span>
      </Heading>

      <SubHeading className="mx-auto mt-6 max-w-lg px-1">{h.subhead}</SubHeading>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
        <Button as={Link} href="/get-started">
          {h.ctaPrimary}
        </Button>
        <Button variant="secondary" as={Link} href="/pricing">
          View pricing
        </Button>
      </div>
      <p className="mt-6 max-w-md text-center text-sm text-gray-600">{h.benefitLine}</p>
    </Container>
  )
}
