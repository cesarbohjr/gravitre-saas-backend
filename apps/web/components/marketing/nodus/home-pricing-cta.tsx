"use client"

import Link from "next/link"
import { Container } from "./container"
import { Button } from "./button"
import { SectionHeading } from "./seciton-heading"
import { SubHeading } from "./subheading"

/**
 * Home pricing slot — Nodus section chrome without inventing plan prices.
 * Authorized pricing lives on /pricing.
 */
export function HomePricingCta() {
  return (
    <Container className="border-divide flex flex-col items-center justify-center border-x px-4 py-16 md:py-24">
      <SectionHeading className="text-center">Simple, honest pricing</SectionHeading>
      <SubHeading className="mx-auto mt-4 max-w-lg">
        See current Gravitre plans on the pricing page. No template demo prices here.
      </SubHeading>
      <Button as={Link} href="/pricing" className="mt-8">
        View pricing
      </Button>
    </Container>
  )
}
