import type { SVGProps } from "react";

export type ChatBubbleOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/**
 * Plain conversation bubble, drawn to match the sharp 24px outline geometry of the
 * licensed Nucleo set already in this folder.
 *
 * The set only shipped "chat-bubble-plus" (NewChatOutline24), which reads as *start
 * a new chat*. The AI Chat launcher restores an existing conversation, so the plus
 * was semantically wrong there. This is the same bubble body and bottom-left tail
 * with the plus removed: (2,4) -> (22,4) -> (22,18) -> (6.25,18) -> (4,22) -> (2,22).
 */
export function ChatBubbleOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: ChatBubbleOutline24Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={24}
      height={24}
      viewBox="0 0 24 24"
      {...props}
    >
      <path
        d="M2 4H22V18H6.25L4 22H2V4Z"
        fill="none"
        stroke="currentColor"
        strokeMiterlimit="10"
        strokeWidth={strokeWidth}
        strokeLinejoin={corners === "round" ? "round" : "miter"}
        strokeLinecap={corners === "round" ? "round" : "square"}
      ></path>
    </svg>
  );
}
