"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowLeft, ArrowRight, Loader2, Mail, CheckCircle2 } from "lucide-react"
import { GravitreMarketingLogoWhite } from "@/components/marketing/gravitre-marketing-logo"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    setIsLoading(false)
    setIsSubmitted(true)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-sm"
      >
        <div className="text-center mb-8">
          <div className="mb-8 flex justify-center">
            <GravitreMarketingLogoWhite height={32} className="h-8" />
          </div>

          {!isSubmitted ? (
            <>
              <h1 className="text-2xl font-semibold text-white">Reset your password</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Enter your email and we&apos;ll send you a link to reset your password.
              </p>
            </>
          ) : (
            <>
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/100/10"
              >
                <CheckCircle2 className="h-8 w-8 text-primary" />
              </motion.div>
              <h1 className="text-2xl font-semibold text-white">Check your email</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                We sent a password reset link to<br />
                <span className="text-white">{email}</span>
              </p>
            </>
          )}
        </div>

        {!isSubmitted ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-muted-foreground mb-1.5">
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
                  className="w-full rounded-lg border border-white/10 bg-card/5 pl-10 pr-4 py-3 text-sm text-white placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="you@company.com"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary/100 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-400 disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
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
            <p className="text-sm text-muted-foreground text-center">
              Didn&apos;t receive the email? Check your spam folder or
            </p>
            <button
              onClick={() => setIsSubmitted(false)}
              className="w-full rounded-lg border border-white/10 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-card/5"
            >
              Try another email
            </button>
          </div>
        )}

        <Link
          href="/login"
          className="mt-6 flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to sign in
        </Link>
      </motion.div>
    </div>
  )
}
