import type { SVGProps } from "react";

export type MicrophoneOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/**
 * Source: Nucleo Sharp "microphone" (owner's licensed nucleoapp.com library) —
 * capsule + stand-arc paths taken from the source asset (its export duplicated
 * the capsule path 3x as opacity-tinted overlays; deduped here to one, since
 * they are stroke-only and render identically). The small base line is a
 * plain geometric accent, not a distinct Nucleo glyph, completing the
 * original "microphone on a stand" reading.
 */
export function MicrophoneOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: MicrophoneOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M8 6C8 3.79086 9.79086 2 12 2C14.2091 2 16 3.79086 16 6V11C16 13.2091 14.2091 15 12 15C9.79086 15 8 13.2091 8 11V6Z" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M4 10V11C4 15.4183 7.58172 19 12 19C16.4183 19 20 15.4183 20 11V10" fill="none" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><line x1="12" y1="19" x2="12" y2="22" fill="none" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="8" y1="22" x2="16" y2="22" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line></svg>
  );
}
