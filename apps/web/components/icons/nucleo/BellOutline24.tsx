import type { SVGProps } from "react";

export type BellOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function BellOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: BellOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="m22,18c-1.657,0-3-1.343-3-3v-6c0-3.866-3.134-7-7-7h0c-3.866,0-7,3.134-7,7v6c0,1.657-1.343,3-3,3h20Z" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="m10.277,22c.346.595.984,1,1.723,1s1.376-.405,1.723-1h-3.445Z" fill="currentColor" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
