import { AgenticIntelligence } from "@/components/marketing/nodus/agentic-intelligence"
import { Benefits } from "@/components/marketing/nodus/benefits"
import { CTA } from "@/components/marketing/nodus/cta"
import { DivideX } from "@/components/marketing/nodus/divide"
import { FAQs } from "@/components/marketing/nodus/faqs"
import { Hero } from "@/components/marketing/nodus/hero"
import { HeroImage } from "@/components/marketing/nodus/hero-image"
import { HowItWorks } from "@/components/marketing/nodus/how-it-works"
import { HomeLogoCloudNote } from "@/components/marketing/nodus/home-logo-cloud-note"
import { HomePricingCta } from "@/components/marketing/nodus/home-pricing-cta"
import { HomeSecurityNote } from "@/components/marketing/nodus/home-security-note"
import { UseCases } from "@/components/marketing/nodus/use-cases"

/**
 * Home — Nodus Agent Template section order (Aceternity preview parity).
 * Orange → green via --brand. Fake prices / Gartner / fake logos omitted.
 * Testimonials omitted until real quotes exist (slot preserved as next section after Benefits).
 */
export default function HomePage() {
  return (
    <main>
      <Hero />
      <DivideX />
      <HeroImage />
      <DivideX />
      <HomeLogoCloudNote />
      <DivideX />
      <HowItWorks />
      <DivideX />
      <AgenticIntelligence />
      <DivideX />
      <UseCases />
      <DivideX />
      <Benefits />
      <DivideX />
      {/* Testimonials: intentionally omitted — no invented quotes */}
      <HomePricingCta />
      <DivideX />
      <HomeSecurityNote />
      <DivideX />
      <FAQs />
      <DivideX />
      <CTA />
    </main>
  )
}
