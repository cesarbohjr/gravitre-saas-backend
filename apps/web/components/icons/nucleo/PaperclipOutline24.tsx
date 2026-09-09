import type { SVGProps } from "react";

export type PaperclipOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "paperclip" (owner's licensed nucleoapp.com library). */
export function PaperclipOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: PaperclipOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M18 6V15.5C18 19.0899 15.0899 22 11.5 22C7.91015 22 5 19.0899 5 15.5V6.5C5 4.01472 7.01472 2 9.5 2C11.9853 2 14 4.01472 14 6.5V14.5C14 15.8807 12.8807 17 11.5 17C10.1193 17 9 15.8807 9 14.5V8" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
