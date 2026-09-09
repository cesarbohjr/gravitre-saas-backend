"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowLeft, ArrowRight, Loader2, Mail, CheckCircle2 } from "lucide-react"
import { GravitreMarketingLogo } from "@/components/marketing/gravitre-marketing-logo"
import { AuthIllustration } from "@/components/marketing/nodus/auth-illustration"
import { Container } from "@/components/marketing/nodus/container"
import { DivideX } from "@/components/marketing/nodus/divide"
import { Heading } from "@/components/marketing/nodus/heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import { GravitrePulse, GravitreResolve } from "@/components/marketing/system"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    // Demo reset flow — wire to auth provider when live.
    await new Promise((resolve) => setTimeout(resolve, 1500))
    setIsLoading(false)
    setIsSubmitted(true)
  }

  return (
    <div className="min-h-screen bg-white">
      <Container className="border-divide min-h-screen border-x py-10 md:py-16">
        <div className="grid grid-cols-1 gap-10 px-4 md:grid-cols-2 md:px-8 lg:gap-16">
          <div className="hidden md:block">
            <AuthIllustration />
          </div>

          <div className="flex w-full items-center justify-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="w-full max-w-[440px]"
            >
              <div className="shadow-aceternity rounded-2xl border border-divide bg-white p-6 sm:p-8 lg:p-10">
                <div className="text-center mb-8">
                  <div className="mb-8 flex justify-center md:hidden">
                    <GravitreMarketingLogo height={32} className="h-8" />
                  </div>

                  {!isSubmitted ? (
                    <>
                      <Heading className="text-left text-2xl lg:text-3xl">Reset your password</Heading>
                      <SubHeading as="p" className="mt-2 text-left">
                        Enter your email and we&apos;ll send you a link to reset your password.
                      </SubHeading>
                    </>
                  ) : (
                    <GravitreResolve>
                      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                        <CheckCircle2 className="h-8 w-8 text-primary" />
                      </div>
                      <Heading className="text-left text-2xl lg:text-3xl">Request recorded</Heading>
                      <SubHeading as="p" className="mt-2 text-left">
                        Demo reset flow — no email is sent from this page. When wired, a reset link
                        would go to{" "}
                        <span className="text-foreground font-medium">{email}</span>.
                      </SubHeading>
                      <p className="mt-3 text-left text-xs text-muted-foreground">Demo reset flow</p>
                    </GravitreResolve>
                  )}
                </div>

                {!isSubmitted ? (
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label
                        htmlFor="email"
                        className="block text-sm font-medium text-foreground mb-1.5"
                      >
                        Email address
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input
                          id="email"
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                          className="w-full rounded-xl border border-border bg-card pl-10 pr-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                          placeholder="you@company.com"
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={isLoading}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90 disabled:opacity-50"
                    >
                      {isLoading ? (
                        <GravitrePulse className="flex items-center justify-center">
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </GravitrePulse>
                      ) : (
                        <>
                          Send reset link
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </button>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <button
                      onClick={() => setIsSubmitted(false)}
                      className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-all hover:bg-muted/50"
                    >
                      Try another email
                    </button>
                  </div>
                )}

                <Link
                  href="/login"
                  className="mt-6 flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to sign in
                </Link>
              </div>
            </motion.div>
          </div>
        </div>
      </Container>
      <DivideX />
    </div>
  )
}
