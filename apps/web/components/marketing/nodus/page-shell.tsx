import { Badge } from "./badge"
import { Container } from "./container"
import { CTA } from "./cta"
import { DivideX } from "./divide"
import { Heading } from "./heading"
import { SubHeading } from "./subheading"

/**
 * Shared Nodus chrome for secondary marketing routes (blog, legal, docs, etc.).
 * Copy must come from authorized product sources — do not invent claims here.
 */
export function MarketingPageHero({
  badge,
  title,
  description,
  children,
  align = "center",
}: {
  badge: string
  title: React.ReactNode
  description?: React.ReactNode
  children?: React.ReactNode
  align?: "center" | "left"
}) {
  const centered = align === "center"
  return (
    <Container
      className={`border-divide flex flex-col border-x px-4 pt-10 pb-10 md:px-8 md:pt-20 md:pb-12 ${
        centered ? "items-center" : "items-start"
      }`}
    >
      <Badge text={badge} />
      <Heading className={`mt-4 ${centered ? "" : "text-left"}`}>{title}</Heading>
      {description ? (
        <SubHeading
          as="p"
          className={`mt-4 max-w-2xl ${centered ? "mx-auto text-center" : "mr-auto text-left"}`}
        >
          {description}
        </SubHeading>
      ) : null}
      {children}
    </Container>
  )
}

export function MarketingRails({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <Container className={`border-divide border-x px-4 py-12 md:px-8 md:py-16 ${className}`}>
      {children}
    </Container>
  )
}

export function MarketingPageEndCta() {
  return (
    <>
      <DivideX />
      <CTA />
    </>
  )
}
