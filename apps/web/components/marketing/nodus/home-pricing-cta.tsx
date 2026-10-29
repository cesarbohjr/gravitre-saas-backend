"use client"

import Link from "next/link"
import { Container } from "./container"
import { Button } from "./button"
import { SectionHeading } from "./seciton-heading"
import { SubHeading } from "./subheading"
import { ReceiptScene } from "./home-scenes"

/**
 * Home pricing slot — Nodus section chrome without inventing plan prices.
 * Authorized pricing lives on /pricing.
 */
export function HomePricingCta() {
  return (
    <Container className="border-divide grid grid-cols-1 items-center gap-10 md:border-x px-4 py-16 md:grid-cols-2 md:px-8 md:py-24">
      <ReceiptScene className="order-2 md:order-1" />
      <div className="order-1 flex flex-col items-center md:order-2 md:items-start">
        <SectionHeading className="text-center md:text-left">Simple, honest pricing</SectionHeading>
        <SubHeading className="mx-auto mt-4 max-w-lg md:mx-0 md:text-left">
          See current Gravitre plans on the pricing page. No template demo prices here.
        </SubHeading>
        <Button as={Link} href="/pricing" className="mt-8">
          View pricing
        </Button>
      </div>
    </Container>
  )
}
