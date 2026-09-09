import { type ReactNode } from "react"
import { Container } from "@/components/marketing/nodus/container"
import { Heading } from "@/components/marketing/nodus/heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import { Badge } from "@/components/marketing/nodus/badge"
import { cn } from "@/lib/utils"

/**
 * Marketing System 4.0 — shared section chrome.
 * Prefer these over one-off heading/card stacks so pages share Nodus rhythm.
 */

export function GravitreSection({
  children,
  className,
  id,
}: {
  children: ReactNode
  className?: string
  id?: string
}) {
  return (
    <Container
      id={id}
      className={cn("border-divide border-x px-4 py-14 md:px-8 md:py-20", className)}
    >
      {children}
    </Container>
  )
}

export function GravitreSectionHeader({
  badge,
  title,
  description,
  align = "left",
  className,
}: {
  badge?: string
  title: ReactNode
  description?: ReactNode
  align?: "left" | "center"
  className?: string
}) {
  const centered = align === "center"
  return (
    <div
      className={cn(
        "mb-10 max-w-2xl",
        centered ? "mx-auto text-center" : "text-left",
        className,
      )}
    >
      {badge ? (
        <div className={cn(centered ? "flex justify-center" : "")}>
          <Badge text={badge} />
        </div>
      ) : null}
      <Heading className={cn("mt-3", centered ? "" : "text-left")}>{title}</Heading>
      {description ? (
        <SubHeading
          as="p"
          className={cn("mt-3", centered ? "mx-auto text-center" : "mr-auto text-left")}
        >
          {description}
        </SubHeading>
      ) : null}
    </div>
  )
}
