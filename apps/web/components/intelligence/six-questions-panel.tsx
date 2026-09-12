"use client"

import { cn } from "@/lib/utils"

/**
 * Phase 2.5 — the real six-question model-card structure from the master
 * brief: WHAT / WHY / LEARNS-FROM / HOW-WELL / WHERE-USED / HOW-TO-IMPROVE.
 *
 * Every answer must be sourced from real, existing data passed in by the
 * caller. When real data doesn't exist for a question, the caller passes
 * `isGap: true` with an honest sentence — this component never invents a
 * plausible-looking answer on its own.
 */
export type SixQuestionKey = "what" | "why" | "learnsFrom" | "howWell" | "whereUsed" | "howToImprove"

export type SixQuestionsAnswer = {
  question: SixQuestionKey
  answer: string
  /** True when `answer` is an honest gap statement, not a real answer. */
  isGap?: boolean
}

const QUESTION_ORDER: SixQuestionKey[] = ["what", "why", "learnsFrom", "howWell", "whereUsed", "howToImprove"]

const QUESTION_LABEL: Record<SixQuestionKey, string> = {
  what: "What does it do?",
  why: "Why does Gravitre use it?",
  learnsFrom: "What does it learn from?",
  howWell: "How well does it work?",
  whereUsed: "Where is it being used?",
  howToImprove: "How can I improve it?",
}

export function SixQuestionsPanel({
  answers,
  className,
}: {
  answers: SixQuestionsAnswer[]
  className?: string
}) {
  const byQuestion = new Map(answers.map((a) => [a.question, a]))
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2", className)}>
      {QUESTION_ORDER.map((question) => {
        const entry = byQuestion.get(question)
        const isGap = entry?.isGap ?? !entry
        return (
          <div
            key={question}
            className={cn(
              "rounded-lg border p-3 text-sm",
              isGap ? "border-dashed border-border/60 bg-secondary/10" : "border-border/60 bg-secondary/20",
            )}
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {QUESTION_LABEL[question]}
            </p>
            <p
              className={cn(
                "mt-1 leading-relaxed",
                isGap ? "italic text-muted-foreground" : "text-foreground/90",
              )}
            >
              {entry?.answer ?? "Not answered yet — no real data for this question."}
            </p>
          </div>
        )
      })}
    </div>
  )
}
