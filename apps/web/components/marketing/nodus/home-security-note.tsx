"use client"

import Link from "next/link"
import { Container } from "./container"
import { SectionHeading } from "./seciton-heading"
import { SubHeading } from "./subheading"
import { ApprovalGateScene } from "./home-scenes"

/**
 * Security slot — Nodus layout density without shipping unverified compliance badges.
 */
export function HomeSecurityNote() {
  return (
    <Container className="border-divide grid grid-cols-1 items-center gap-10 md:border-x px-4 py-16 md:grid-cols-2 md:px-8 md:py-24">
      <div className="flex flex-col items-center md:items-start">
        <SectionHeading className="text-center md:text-left">Governed by design</SectionHeading>
        <SubHeading className="mx-auto mt-4 max-w-lg md:mx-0 md:text-left">
          Permissions, approvals, audit trails, and human oversight stay part of every action.
          Full security details are on our security page.
        </SubHeading>
        <Link
          href="/security"
          className="mt-8 text-sm font-medium text-brand underline-offset-4 hover:underline"
        >
          Read security →
        </Link>
      </div>
      <ApprovalGateScene />
    </Container>
  )
}
