import type { SVGProps } from "react";

export type BranchMergeOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function BranchMergeOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: BranchMergeOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M16 19L21 14L16 9" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M3 14H21H20.5" stroke="currentColor" strokeWidth={strokeWidth} fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M3 5H6.03875C6.64632 5 7.22094 5.27618 7.60049 5.75061L11 10" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
