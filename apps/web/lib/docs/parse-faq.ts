import GithubSlugger from "github-slugger"

export type FaqQuestion = {
  id: string
  question: string
  /** Raw markdown answer body (may contain links/inline formatting). */
  answer: string
  /** Plain-text version of question + answer, used for client-side search. */
  searchText: string
}

export type FaqSection = {
  id: string
  title: string
  /** Section-level prose that appears before any `###` question (optional). */
  intro: string
  questions: FaqQuestion[]
}

/** Strip markdown link/emphasis syntax down to readable text for search matching. */
function toPlainText(markdown: string): string {
  return markdown
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // links -> label
    .replace(/[*_`#>]/g, "") // emphasis / code / heading marks
    .replace(/\s+/g, " ")
    .trim()
}

/**
 * Parse a FAQ MDX body (already frontmatter-stripped) into sections of
 * question/answer pairs. Structure: `## Section` -> `### Question` -> answer.
 */
export function parseFaq(content: string): FaqSection[] {
  const slugger = new GithubSlugger()
  const lines = content.split("\n")

  const sections: FaqSection[] = []
  let currentSection: FaqSection | null = null
  let currentQuestion: FaqQuestion | null = null
  let buffer: string[] = []

  const flushAnswer = () => {
    if (currentQuestion) {
      currentQuestion.answer = buffer.join("\n").trim()
      currentQuestion.searchText = toPlainText(
        `${currentQuestion.question} ${currentQuestion.answer}`,
      ).toLowerCase()
      currentQuestion = null
    } else if (currentSection) {
      currentSection.intro = `${currentSection.intro}\n${buffer.join("\n")}`.trim()
    }
    buffer = []
  }

  for (const line of lines) {
    const sectionMatch = /^##\s+(?!#)(.+)$/.exec(line)
    const questionMatch = /^###\s+(.+)$/.exec(line)

    if (sectionMatch) {
      flushAnswer()
      currentSection = {
        id: slugger.slug(sectionMatch[1]),
        title: sectionMatch[1].trim(),
        intro: "",
        questions: [],
      }
      sections.push(currentSection)
      continue
    }

    if (questionMatch && currentSection) {
      flushAnswer()
      currentQuestion = {
        id: slugger.slug(questionMatch[1]),
        question: questionMatch[1].trim(),
        answer: "",
        searchText: "",
      }
      currentSection.questions.push(currentQuestion)
      continue
    }

    buffer.push(line)
  }

  flushAnswer()

  return sections.filter((s) => s.questions.length > 0 || s.intro.length > 0)
}
