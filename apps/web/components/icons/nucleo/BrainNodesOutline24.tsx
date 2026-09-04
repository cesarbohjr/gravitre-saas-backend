import type { SVGProps } from "react";

export type BrainNodesOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function BrainNodesOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: BrainNodesOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M3.40118 12.0466L3.5 12C2.61705 12.3858 2 13.4748 2 14.5C2 15.7536 2.9227 16.7917 4.12602 16.9722C3.50585 22.4483 10.8507 23.6333 11.97 19.129L12 16H16L18.129 18.129" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M7 13H6C3.79086 13 2.5 11.2091 2.5 9C2.5 6.5 4.51867 5 7 5C7 3.48283 7.7632 2 9.5 2C10.6755 2 11.7087 2.81129 11.9785 3.90449L12 8H16L18 6" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M19 21C20.1046 21 21 20.1046 21 19C21 17.8954 20.1046 17 19 17C17.8954 17 17 17.8954 17 19C17 20.1046 17.8954 21 19 21Z" fill="currentColor" data-color="color-2" data-cap="butt" data-stroke="none"></path> <path d="M19 7C20.1046 7 21 6.10457 21 5C21 3.89543 20.1046 3 19 3C17.8954 3 17 3.89543 17 5C17 6.10457 17.8954 7 19 7Z" fill="currentColor" data-color="color-2" data-cap="butt" data-stroke="none"></path> <path d="M13 12H20" stroke="currentColor" strokeWidth={strokeWidth} fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M21 14C22.1046 14 23 13.1046 23 12C23 10.8954 22.1046 10 21 10C19.8954 10 19 10.8954 19 12C19 13.1046 19.8954 14 21 14Z" fill="currentColor" data-color="color-2" data-cap="butt" data-stroke="none"></path></svg>
  );
}
