import type { SVGProps } from "react";

export type PaperclipOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function PaperclipOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: PaperclipOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="m20,12.5l-8.5,8.5c-1.933,1.933-5.067,1.933-7,0h0c-1.933-1.933-1.933-5.067,0-7l9.19-9.19c1.243-1.243,3.257-1.243,4.5,0h0c1.243,1.243,1.243,3.257,0,4.5l-8.19,8.19" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
