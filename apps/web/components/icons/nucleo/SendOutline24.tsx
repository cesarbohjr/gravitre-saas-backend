import type { SVGProps } from "react";

export type SendOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "paper-plane-2" (owner's licensed nucleoapp.com library). */
export function SendOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: SendOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M21 3L10 14" fill="none" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M21 3L15 22H14.5L10 14L2 9.5L2.00004 9L21 3Z" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
