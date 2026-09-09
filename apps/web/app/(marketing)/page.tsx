import dynamic from "next/dynamic"
import { Hero } from "@/components/marketing/nodus/hero"
import { HeroImage } from "@/components/marketing/nodus/hero-image"
import { DivideX } from "@/components/marketing/nodus/divide"

/**
 * Below-fold marketing sections — code-split so framer-motion / tab skeletons
 * do not compete with LCP on the home hero (Lighthouse CI desktop preset).
 */
const HomeLogoCloudNote = dynamic(() =>
  import("@/components/marketing/nodus/home-logo-cloud-note").then((m) => ({
    default: m.HomeLogoCloudNote,
  })),
)
const HowItWorks = dynamic(() =>
  import("@/components/marketing/nodus/how-it-works").then((m) => ({
    default: m.HowItWorks,
  })),
)
const AgenticIntelligence = dynamic(() =>
  import("@/components/marketing/nodus/agentic-intelligence").then((m) => ({
    default: m.AgenticIntelligence,
  })),
)
const UseCases = dynamic(() =>
  import("@/components/marketing/nodus/use-cases").then((m) => ({
    default: m.UseCases,
  })),
)
const Benefits = dynamic(() =>
  import("@/components/marketing/nodus/benefits").then((m) => ({
    default: m.Benefits,
  })),
)
const HomePricingCta = dynamic(() =>
  import("@/components/marketing/nodus/home-pricing-cta").then((m) => ({
    default: m.HomePricingCta,
  })),
)
const HomeSecurityNote = dynamic(() =>
  import("@/components/marketing/nodus/home-security-note").then((m) => ({
    default: m.HomeSecurityNote,
  })),
)
const FAQs = dynamic(() =>
  import("@/components/marketing/nodus/faqs").then((m) => ({
    default: m.FAQs,
  })),
)
const CTA = dynamic(() =>
  import("@/components/marketing/nodus/cta").then((m) => ({
    default: m.CTA,
  })),
)

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
