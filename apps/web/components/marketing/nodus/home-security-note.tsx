"use client"

import Link from "next/link"
import { Container } from "./container"
import { SectionHeading } from "./seciton-heading"
import { SubHeading } from "./subheading"

/**
 * Security slot — Nodus layout density without shipping unverified compliance badges.
 */
export function HomeSecurityNote() {
  return (
    <Container className="border-divide flex flex-col items-center justify-center border-x px-4 py-16 md:py-24">
      <SectionHeading className="text-center">Governed by design</SectionHeading>
      <SubHeading className="mx-auto mt-4 max-w-lg">
        Permissions, approvals, audit trails, and human oversight stay part of every action.
        Full security details are on our security page.
      </SubHeading>
      <Link
        href="/security"
        className="mt-8 text-sm font-medium text-brand underline-offset-4 hover:underline"
      >
        Read security →
      </Link>
    </Container>
  )
}
