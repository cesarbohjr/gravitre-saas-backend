"use client"

import dynamic from "next/dynamic"

const HeroImage = dynamic(
  () => import("./hero-image").then((m) => ({ default: m.HeroImage })),
  {
    ssr: false,
    loading: () => (
      <div
        className="border-divide aspect-[1024/575] w-full border-x bg-gray-100 dark:bg-neutral-800"
        aria-hidden
      />
    ),
  },
)

/** Client-only hero screenshot — keeps dashboard asset off the SSR/LCP path. */
export function HeroImageLazy() {
  return <HeroImage />
}
