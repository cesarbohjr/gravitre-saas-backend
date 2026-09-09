"use client"

import dynamic from "next/dynamic"
import { useEffect, useRef, useState } from "react"

const HeroImage = dynamic(
  () => import("./hero-image").then((m) => ({ default: m.HeroImage })),
  { ssr: false },
)

function HeroImagePlaceholder() {
  return (
    <div
      className="border-divide aspect-[1024/575] w-full border-x bg-gray-100 dark:bg-neutral-800"
      aria-hidden
    />
  )
}

/**
 * Loads the dashboard screenshot only when scrolled into view — keeps it off
 * the Lighthouse LCP path while the full-viewport hero text paints first.
 */
export function HeroImageLazy() {
  const hostRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = hostRef.current
    if (!node) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: "120px 0px" },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return <div ref={hostRef}>{visible ? <HeroImage /> : <HeroImagePlaceholder />}</div>
}
