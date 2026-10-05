"use client"

import { Fragment, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import {
  toTextBlocks,
  type DeliverableSection,
  type DeliverableSectionKind,
  type ParsedDeliverable,
} from "@/lib/assignment-deliverable"

const SECTION_ICON: Record<DeliverableSectionKind, IconName> = {
  summary: "fileText",
  recommendations: "checkCircle",
  risks: "shieldAlert",
  next_steps: "listTodo",
  sources: "link",
}

/** `**bold**` only; everything else renders as literal text. */
function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
          <strong key={index} className="font-semibold text-foreground">
            {part.slice(2, -2)}
          </strong>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  )
}

function SectionBlock({ section }: { section: DeliverableSection }) {
  const ordered = section.kind === "next_steps"
  const ListTag = ordered ? "ol" : "ul"
  return (
    <section aria-labelledby={`deliverable-${section.kind}`} className="flex flex-col gap-2" data-section={section.kind}>
      <h3 id={`deliverable-${section.kind}`} className="flex items-center gap-2 text-[14px] font-semibold text-foreground">
        <Icon
          name={SECTION_ICON[section.kind]}
          size="sm"
          className={cn("shrink-0", section.kind === "risks" ? "text-[color:var(--g-approval)]" : "text-muted-foreground")}
        />
        {section.label}
        {section.items.length > 1 ? (
          <span className="text-[12px] font-normal tabular-nums text-muted-foreground">{section.items.length}</span>
        ) : null}
      </h3>
      {section.paragraphs.map((paragraph, index) => (
        <p key={index} className="text-pretty text-[14px] leading-relaxed text-foreground">
          <InlineText text={paragraph} />
        </p>
      ))}
      {section.items.length > 0 ? (
        <ListTag
          className={cn(
            "flex flex-col gap-1.5 pl-5 text-[14px] leading-relaxed text-foreground",
            ordered ? "list-decimal" : "list-disc marker:text-muted-foreground",
          )}
        >
          {section.items.map((item, index) => (
            <li key={index} className="break-words pl-1">
              <InlineText text={item} />
            </li>
          ))}
        </ListTag>
      ) : null}
    </section>
  )
}

function TextReport({ text }: { text: string }) {
  const blocks = toTextBlocks(text)
  if (blocks.length === 0) return <p className="text-[14px] text-muted-foreground">The agent returned an empty response.</p>
  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <h3 key={index} className="pt-1 text-[14px] font-semibold text-foreground">
              {block.text}
            </h3>
          )
        }
        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul"
          return (
            <ListTag
              key={index}
              className={cn(
                "flex flex-col gap-1.5 pl-5 text-[14px] leading-relaxed text-foreground",
                block.ordered ? "list-decimal" : "list-disc marker:text-muted-foreground",
              )}
            >
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="break-words pl-1">
                  <InlineText text={item} />
                </li>
              ))}
            </ListTag>
          )
        }
        return (
          <p key={index} className="text-pretty break-words text-[14px] leading-relaxed text-foreground">
            <InlineText text={block.text} />
          </p>
        )
      })}
    </div>
  )
}

function Disclosure({
  summary,
  count,
  children,
  defaultOpen = false,
  name,
}: {
  summary: string
  count?: number
  children: ReactNode
  defaultOpen?: boolean
  name: string
}) {
  return (
    <details
      open={defaultOpen}
      data-disclosure={name}
      className="group rounded-[var(--g-radius-control,8px)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]"
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 text-[13px] font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:min-h-9 [&::-webkit-details-marker]:hidden">
        <Icon name="chevronRight" size="sm" className="shrink-0 text-muted-foreground transition-transform group-open:rotate-90 motion-reduce:transition-none" />
        {summary}
        {count != null ? <span className="tabular-nums text-muted-foreground">{count}</span> : null}
      </summary>
      <div className="border-t border-[color:var(--g-border-subtle)] px-3 py-3">{children}</div>
    </details>
  )
}

export function OriginalDataDisclosure({ parsed }: { parsed: ParsedDeliverable }) {
  const [copied, setCopied] = useState(false)
  const body = parsed.originalJson ?? parsed.original
  if (!body.trim()) return null
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(body)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error("Could not copy to the clipboard")
    }
  }
  return (
    <Disclosure summary={parsed.format === "structured" ? "View original data" : "View original text"} name="original">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[12px] text-muted-foreground">
            {parsed.format === "structured" ? "Formatted JSON exactly as returned by the agent." : "Unformatted text as returned."}
          </p>
          <Button type="button" size="sm" variant="ghost" className="h-8 gap-1.5 text-[12px]" onClick={() => void copy()}>
            <Icon name={copied ? "check" : "copy"} size="xs" />
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-[6px] bg-background p-3 font-mono text-[12px] leading-relaxed text-foreground">
          {body}
        </pre>
      </div>
    </Disclosure>
  )
}

export function DeliverableReport({ parsed }: { parsed: ParsedDeliverable }) {
  return (
    <div className="flex flex-col gap-5" data-deliverable-format={parsed.format}>
      {parsed.format === "structured" ? (
        <>
          {parsed.prefixLabel ? (
            <p className="text-[12px] text-muted-foreground">
              Structured output · <span className="text-foreground">{parsed.prefixLabel}</span>
            </p>
          ) : null}
          {parsed.sections.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">
              The agent returned structured fields without a summary. They are listed below.
            </p>
          ) : (
            parsed.sections.map((section) => <SectionBlock key={section.sourceKey} section={section} />)
          )}
          {parsed.fields.length > 0 ? (
            <Disclosure
              summary="Additional details"
              count={parsed.fields.length}
              name="fields"
              defaultOpen={parsed.sections.length === 0}
            >
              <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[minmax(120px,max-content)_minmax(0,1fr)]">
                {parsed.fields.map((field) => (
                  <div key={field.key} className="contents">
                    <dt className="text-[12px] font-medium text-muted-foreground sm:pt-0.5" title={field.key}>
                      {field.label}
                    </dt>
                    <dd className="min-w-0 text-[13px] text-foreground">
                      {field.value === null ? (
                        <span className="text-muted-foreground">Empty (null)</span>
                      ) : field.multiline ? (
                        <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed">
                          {field.value}
                        </pre>
                      ) : (
                        <span className="break-words">{field.value}</span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </Disclosure>
          ) : null}
        </>
      ) : (
        <TextReport text={parsed.original} />
      )}
    </div>
  )
}
