const BV_PATTERN = /BV[0-9A-Za-z]{10}/

const SUPPORTED_BILIBILI_HOSTS = new Set([
  'bilibili.com',
  'www.bilibili.com',
  'm.bilibili.com',
  'b23.tv',
])

export interface NormalizedBilibiliInput {
  url: string
  bvid: string | null
}

const INVALID_INPUT: NormalizedBilibiliInput = { url: '', bvid: null }

export function normalizeBilibiliInput(input: string): NormalizedBilibiliInput {
  const trimmed = input.trim()
  if (!trimmed) return INVALID_INPUT

  const bareBv = trimmed.match(BV_PATTERN)?.[0]
  if (bareBv && trimmed === bareBv) {
    return {
      url: `https://www.bilibili.com/video/${bareBv}`,
      bvid: bareBv,
    }
  }

  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)
    ? trimmed
    : `https://${trimmed}`

  let parsed: URL
  try {
    parsed = new URL(withScheme)
  } catch {
    return INVALID_INPUT
  }

  const host = parsed.hostname.toLowerCase()
  if (!SUPPORTED_BILIBILI_HOSTS.has(host)) return INVALID_INPUT

  if (host === 'b23.tv') {
    return { url: parsed.toString(), bvid: null }
  }

  if (!parsed.pathname.includes('/video/')) return INVALID_INPUT

  const bvid = parsed.pathname.match(BV_PATTERN)?.[0] ?? null
  if (!bvid) return INVALID_INPUT

  if (host === 'm.bilibili.com') {
    parsed.hostname = 'www.bilibili.com'
  }

  return { url: parsed.toString(), bvid }
}
