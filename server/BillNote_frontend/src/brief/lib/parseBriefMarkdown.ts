export interface BriefVerdict {
  score: number | null
  audience: string[]
  notFor: string[]
}

export interface BriefChapter {
  time: string
  seconds: number
  title: string
}

export interface BriefTerm {
  term: string
  explanation: string
}

export interface BriefDocument {
  oneLine: string
  verdict: BriefVerdict
  summaryItems: string[]
  chapters: BriefChapter[]
  terms: BriefTerm[]
  actions: string[]
  rawMarkdown: string
}

const SECTION_NAMES = {
  oneLine: '一句话结论',
  verdict: '是否值得看',
  summary: '核心摘要',
  chapters: '章节',
  terms: '术语',
  actions: '行动清单',
} as const

function cleanInlineMarkdown(value: string): string {
  return value
    .replace(/^\s{0,3}(?:[-*+]|\d+[.)])\s+/, '')
    .replace(/\*\*|__/g, '')
    .replace(/`/g, '')
    .trim()
}

function splitSections(markdown: string): Map<string, string> {
  const sections = new Map<string, string>()
  const matches = [...markdown.matchAll(/^##\s+(.+?)\s*$/gm)]

  matches.forEach((match, index) => {
    const name = cleanInlineMarkdown(match[1])
    const start = (match.index ?? 0) + match[0].length
    const end =
      index + 1 < matches.length
        ? (matches[index + 1].index ?? markdown.length)
        : markdown.length
    sections.set(name, markdown.slice(start, end).trim())
  })

  return sections
}

function sectionValue(sections: Map<string, string>, name: string): string {
  return sections.get(name) ?? ''
}

function nonEmptyLines(value: string): string[] {
  return value
    .split('\n')
    .map(cleanInlineMarkdown)
    .filter(Boolean)
}

function listItems(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => /^(?:[-*+]|\d+[.)])\s+/.test(line))
    .map(cleanInlineMarkdown)
    .filter(Boolean)
}

function paragraphs(value: string): string[] {
  return value
    .split(/\n\s*\n/)
    .map((paragraph) => cleanInlineMarkdown(paragraph.replace(/\n/g, ' ')))
    .filter(Boolean)
}

function findValue(value: string, labels: string[]): string {
  const labelsPattern = labels.join('|')
  const match = value.match(new RegExp(`(?:${labelsPattern})\\s*[:：]\\s*(.+)`, 'i'))
  return cleanInlineMarkdown(match?.[1] ?? '')
}

function splitList(value: string): string[] {
  return value
    .split(/[、，,；;]/)
    .map(cleanInlineMarkdown)
    .filter(Boolean)
}

function parseVerdict(value: string): BriefVerdict {
  const scoreMatch = value.match(/(?:评分\s*[:：]\s*)?(\d+(?:\.\d+)?)\s*\/\s*10/)
  const audience = splitList(findValue(value, ['适合']))
  const notFor = splitList(findValue(value, ['不适合']))

  return {
    score: scoreMatch ? Number(scoreMatch[1]) : null,
    audience,
    notFor,
  }
}

function parseChapters(value: string): BriefChapter[] {
  const chapters: BriefChapter[] = []

  for (const line of nonEmptyLines(value)) {
    const match = line.match(/^\[(\d{1,2}):(\d{2})(?::(\d{2}))?]\s*(.+)$/)
    if (!match) continue

    const first = Number(match[1])
    const second = Number(match[2])
    const third = match[3] === undefined ? null : Number(match[3])
    const seconds =
      third === null
        ? first * 60 + second
        : first * 3600 + second * 60 + third

    chapters.push({
      time: match[0].slice(1, match[0].indexOf(']')),
      seconds,
      title: cleanInlineMarkdown(match[4]),
    })
  }

  return chapters
}

function parseTerms(value: string): BriefTerm[] {
  return nonEmptyLines(value)
    .filter((line) => line !== '无')
    .map((line) => {
      const separatorIndex = Math.max(line.indexOf('：'), line.indexOf(':'))
      if (separatorIndex <= 0) return null

      const term = line.slice(0, separatorIndex).trim()
      const explanation = line.slice(separatorIndex + 1).trim()
      return term && explanation ? { term, explanation } : null
    })
    .filter((item): item is BriefTerm => item !== null)
}

function fallbackOneLine(markdown: string): string {
  const withoutSource = markdown.replace(/^>\s*来源链接[:：].*$/gm, '')
  const candidates = lotsOfReadableLines(withoutSource)
  return candidates[0] ?? ''
}

function lotsOfReadableLines(markdown: string): string[] {
  return markdown
    .split('\n')
    .map((line) => line.trim())
    .filter(
      (line) =>
        line &&
        !line.startsWith('#') &&
        !line.startsWith('>') &&
        !line.startsWith('```'),
    )
    .map(cleanInlineMarkdown)
}

export function parseBriefMarkdown(markdown: string): BriefDocument {
  const sections = splitSections(markdown)
  const oneLine =
    paragraphs(sectionValue(sections, SECTION_NAMES.oneLine))[0] ??
    fallbackOneLine(markdown)

  return {
    oneLine,
    verdict: parseVerdict(sectionValue(sections, SECTION_NAMES.verdict)),
    summaryItems: listItems(sectionValue(sections, SECTION_NAMES.summary)),
    chapters: parseChapters(sectionValue(sections, SECTION_NAMES.chapters)),
    terms: parseTerms(sectionValue(sections, SECTION_NAMES.terms)),
    actions: listItems(sectionValue(sections, SECTION_NAMES.actions)),
    rawMarkdown: markdown,
  }
}
