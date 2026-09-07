"use client"

import { Container } from "./container"
import { SubHeading } from "./subheading"

/**
 * Logo cloud slot — keep Nodus spacing without fake customer logos.
 * Real logos can replace this when authorized.
 */
export function HomeLogoCloudNote() {
  return (
    <Container className="border-divide flex flex-col items-center justify-center border-x px-4 py-10 md:py-14">
      <SubHeading className="max-w-xl">
        Connects to the tools you already use — Salesforce, HubSpot, Slack, and more.
      </SubHeading>
    </Container>
  )
}
