import localFont from "next/font/local"

/** Marketing subset — Regular + Medium only (hero h1, body copy). */
export const interDisplayMarketing = localFont({
  src: [
    { path: "./InterDisplay-Regular.ttf", weight: "400", style: "normal" },
    { path: "./InterDisplay-Medium.ttf", weight: "500", style: "normal" },
  ],
  variable: "--font-inter-display",
  display: "optional",
  preload: true,
})
