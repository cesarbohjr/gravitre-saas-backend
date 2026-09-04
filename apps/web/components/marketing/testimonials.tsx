"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronLeft, ChevronRight, Star, Quote } from "lucide-react"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"
import { PlatformTruthBanner } from "@/components/marketing/platform-truth-banner"

interface Testimonial {
  quote: string
  author: string
  role: string
  company: string
  avatar?: string
  highlight?: string
}

const defaultTestimonials: Testimonial[] = [
  {
    quote: "Gravitre is a strong signal of how enterprise automation will evolve. It is an early adopter of the agentic approach, which will become increasingly effective, trusted, and prominent.",
    author: "Marc Chen",
    role: "VP of Engineering",
    company: "TechFlow",
    highlight: "10,000+ businesses trust Gravitre"
  },
  {
    quote: "The AI agents are user-friendly, easy to customize, and have been effectively serving our customers for nearly two years. The ROI has been incredible.",
    author: "Sarah Martinez",
    role: "Director of Operations",
    company: "DataSync Inc",
  },
  {
    quote: "Gravitre gave us a powerful, flexible way to launch our AI automation without the complexity we saw in other platforms. The customization options let us match our brand voice perfectly.",
    author: "James Wilson",
    role: "CTO",
    company: "CloudBase",
  },
  {
    quote: "This is an excellent AI solution for businesses. Onboarding is fast, and training the agents is easy even with a lot of information. For our team, the experience is smooth and friction-free.",
    author: "Emily Rodriguez",
    role: "Head of Product",
    company: "Nexus Labs",
  },
  {
    quote: "The platform has transformed how our team handles repetitive tasks. We've reduced manual work by 70% while improving accuracy. The agents just work.",
    author: "Michael Torres",
    role: "COO",
    company: "Quantum Systems",
  },
]

// Horizontal scrolling testimonials - Chatbase style
export function TestimonialsMarquee({ testimonials = defaultTestimonials }: { testimonials?: Testimonial[] }) {
  if (!SHOW_MARKETING_TESTIMONIALS) return null
  // Double the testimonials for seamless loop
  const allTestimonials = [...testimonials, ...testimonials]
  
  return (
    <div className="relative overflow-hidden py-4">
      {/* Fade edges */}
      <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-white to-transparent z-10" />
      <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-white to-transparent z-10" />
      
      <motion.div
        className="flex gap-6"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
      >
        {allTestimonials.map((testimonial, i) => (
          <div
            key={`${testimonial.author}-${i}`}
            className="shrink-0 w-[400px] p-6 rounded-2xl bg-card border border-border shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="h-12 w-12 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white font-semibold text-lg shrink-0">
                {testimonial.author.charAt(0)}
              </div>
              <div>
                <div className="font-semibold text-foreground">{testimonial.author}</div>
                <div className="text-sm text-muted-foreground">{testimonial.role}</div>
                <div className="text-sm text-primary font-medium">{testimonial.company}</div>
              </div>
            </div>
            <p className="text-muted-foreground text-sm leading-relaxed">
              &ldquo;{testimonial.quote}&rdquo;
            </p>
          </div>
        ))}
      </motion.div>
    </div>
  )
}

// Featured testimonials grid with stats
export function TestimonialsGrid({ testimonials = defaultTestimonials }: { testimonials?: Testimonial[] }) {
  if (!SHOW_MARKETING_TESTIMONIALS) return null
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Large featured testimonial */}
      <div className="lg:col-span-2 lg:row-span-2 p-8 rounded-2xl bg-gradient-to-br from-primary/10 to-teal-50 border border-primary/20">
        <Quote className="h-10 w-10 text-emerald-300 mb-6" />
        <p className="text-xl text-foreground leading-relaxed mb-8">
          &ldquo;{testimonials[0].quote}&rdquo;
        </p>
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-full bg-gradient-to-br from-primary/100 to-teal-600 flex items-center justify-center text-white font-bold text-xl">
            {testimonials[0].author.charAt(0)}
          </div>
          <div>
            <div className="font-semibold text-foreground">{testimonials[0].author}</div>
            <div className="text-sm text-muted-foreground">{testimonials[0].role}, {testimonials[0].company}</div>
          </div>
        </div>
        {testimonials[0].highlight && (
          <div className="mt-8 pt-6 border-t border-primary/20">
            <div className="text-3xl font-bold text-primary">{testimonials[0].highlight}</div>
          </div>
        )}
      </div>

      {/* Smaller testimonials */}
      {testimonials.slice(1, 5).map((testimonial, i) => (
        <motion.div
          key={testimonial.author}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.1 }}
          className="p-6 rounded-2xl bg-card border border-border hover:border-border hover:shadow-md transition-all"
        >
          <div className="flex mb-3">
            {[1, 2, 3, 4, 5].map((star) => (
              <Star key={star} className="h-4 w-4 fill-amber-400 text-amber-400" />
            ))}
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed mb-4 line-clamp-4">
            &ldquo;{testimonial.quote}&rdquo;
          </p>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground font-semibold text-sm">
              {testimonial.author.charAt(0)}
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">{testimonial.author}</div>
              <div className="text-xs text-muted-foreground">{testimonial.company}</div>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

// Product-truth stats — no invented customer counts or ROI figures
export function SocialProofBanner() {
  return (
    <PlatformTruthBanner note="Product mechanics we ship today — not customer counts or invented ROI." />
  )
}

// Logo cloud component
export function LogoCloud() {
  const companies = [
    "Acme Corp", "TechFlow", "DataSync", "CloudBase", "Quantum", "Nexus", 
    "Vertex AI", "Pinnacle", "Horizon", "Nova Labs"
  ]

  return (
    <div className="py-16 border-y border-border bg-card">
      <div className="mx-auto max-w-7xl px-6">
        <motion.p 
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center text-sm font-medium text-muted-foreground mb-10"
        >
          Trusted by innovative teams at
        </motion.p>
        
        <div className="relative overflow-hidden">
          {/* Fade edges */}
          <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-white to-transparent z-10" />
          <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-white to-transparent z-10" />
          
          <motion.div
            className="flex items-center gap-16"
            animate={{ x: ["0%", "-50%"] }}
            transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
          >
            {[...companies, ...companies].map((name, i) => (
              <span
                key={`${name}-${i}`}
                className="shrink-0 text-xl font-semibold text-muted-foreground hover:text-muted-foreground transition-colors cursor-default whitespace-nowrap"
              >
                {name}
              </span>
            ))}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

// Full-width testimonials carousel with navigation
export function TestimonialsCarouselFull({ testimonials = defaultTestimonials }: { testimonials?: Testimonial[] }) {
  if (!SHOW_MARKETING_TESTIMONIALS) return null
  return <TestimonialsCarouselFullActive testimonials={testimonials} />
}

function TestimonialsCarouselFullActive({ testimonials }: { testimonials: Testimonial[] }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [direction, setDirection] = useState(0)

  const goToPrevious = () => {
    setDirection(-1)
    setActiveIndex((prev) => (prev - 1 + testimonials.length) % testimonials.length)
  }

  const goToNext = () => {
    setDirection(1)
    setActiveIndex((prev) => (prev + 1) % testimonials.length)
  }

  useEffect(() => {
    if (testimonials.length === 0) return
    const timer = setInterval(() => {
      setDirection(1)
      setActiveIndex((prev) => (prev + 1) % testimonials.length)
    }, 8000)
    return () => clearInterval(timer)
  }, [testimonials.length])

  return (
    <div className="relative">
      <div className="overflow-hidden">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={activeIndex}
            custom={direction}
            initial={{ opacity: 0, x: direction > 0 ? 100 : -100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction > 0 ? -100 : 100 }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
            className="bg-card rounded-3xl border border-border p-8 md:p-12 shadow-lg"
          >
            <div className="flex flex-col md:flex-row items-start md:items-center gap-8">
              <div className="shrink-0">
                <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg shadow-emerald-500/20">
                  {testimonials[activeIndex].author.charAt(0)}
                </div>
              </div>
              <div className="flex-1">
                <div className="flex mb-4">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star key={star} className="h-5 w-5 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <blockquote className="text-xl md:text-2xl text-foreground leading-relaxed mb-6">
                  &ldquo;{testimonials[activeIndex].quote}&rdquo;
                </blockquote>
                <div>
                  <div className="font-semibold text-foreground text-lg">{testimonials[activeIndex].author}</div>
                  <div className="text-muted-foreground">
                    {testimonials[activeIndex].role}, {testimonials[activeIndex].company}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-8">
        <div className="flex items-center gap-2">
          {testimonials.map((_, i) => (
            <button
              key={i}
              onClick={() => {
                setDirection(i > activeIndex ? 1 : -1)
                setActiveIndex(i)
              }}
              className={`h-2 rounded-full transition-all ${
                i === activeIndex ? "w-8 bg-primary" : "w-2 bg-muted hover:bg-muted-foreground/40"
              }`}
            />
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevious}
            className="h-10 w-10 rounded-full border border-border bg-card flex items-center justify-center text-muted-foreground hover:bg-muted/50 hover:border-border transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <button
            onClick={goToNext}
            className="h-10 w-10 rounded-full border border-border bg-card flex items-center justify-center text-muted-foreground hover:bg-muted/50 hover:border-border transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
