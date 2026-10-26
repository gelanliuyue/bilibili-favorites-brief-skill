import { describe, expect, it } from 'vitest'
import { parseBriefMarkdown } from './parseBriefMarkdown'

const completeMarkdown = `# 视频标题

> 来源链接：https://www.bilibili.com/video/BV1xx411c7mD

## 一句话结论
真正有用的不是收藏视频，而是把教程拆成可检索的知识卡。

## 是否值得看
评分：8.6/10
适合：准备建立知识库的人、需要快速复习的人
不适合：寻找具体软件安装步骤的人

## 核心摘要
- 先判断视频是否值得投入时间。
- 再把章节和知识点整理成结构。
- 最后保留时间点，方便回到原片。

## 章节
- [00:12] 为什么收藏会变成负担：收藏本身不产生理解。
- [08:40] 三种提炼方法：适合不同长度的教程。
- [21:15] 如何复习：从摘要跳回关键片段。

## 术语
- 知识卡：用一句话结论、结构和来源组成的可复习笔记。
- 时间锚点：可以点击并跳回视频指定位置的秒数。

## 行动清单
1. 挑选一个收藏了很久的教程。
2. 生成摘要后只完整观看评分最高的章节。
`

describe('parseBriefMarkdown', () => {
  it('extracts the complete mobile brief document', () => {
    const result = parseBriefMarkdown(completeMarkdown)

    expect(result.oneLine).toBe(
      '真正有用的不是收藏视频，而是把教程拆成可检索的知识卡。',
    )
    expect(result.verdict.score).toBe(8.6)
    expect(result.verdict.audience).toEqual([
      '准备建立知识库的人',
      '需要快速复习的人',
    ])
    expect(result.verdict.notFor).toEqual(['寻找具体软件安装步骤的人'])
    expect(result.summaryItems).toHaveLength(3)
    expect(result.chapters[1]).toMatchObject({
      time: '08:40',
      seconds: 520,
      title: '三种提炼方法：适合不同长度的教程。',
    })
    expect(result.terms[0]).toEqual({
      term: '知识卡',
      explanation: '用一句话结论、结构和来源组成的可复习笔记。',
    })
    expect(result.actions).toEqual([
      '挑选一个收藏了很久的教程。',
      '生成摘要后只完整观看评分最高的章节。',
    ])
    expect(result.rawMarkdown).toBe(completeMarkdown)
  })

  it('falls back to the first paragraph when structured headings are missing', () => {
    const result = parseBriefMarkdown(`# 视频标题

这段视频介绍了一个不需要完整观看也能理解教程的方法。

更多普通内容。`)

    expect(result.oneLine).toBe(
      '这段视频介绍了一个不需要完整观看也能理解教程的方法。',
    )
    expect(result.summaryItems).toEqual([])
    expect(result.chapters).toEqual([])
    expect(result.terms).toEqual([])
    expect(result.actions).toEqual([])
    expect(result.verdict).toEqual({
      score: null,
      audience: [],
      notFor: [],
    })
  })
})
