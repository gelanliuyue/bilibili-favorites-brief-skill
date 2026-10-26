import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefResult } from './BriefResult'
import { parseBriefMarkdown } from '../lib/parseBriefMarkdown'

vi.mock('./BriefMindMap', () => ({
  BriefMindMap: ({ markdown }: { markdown: string }) => (
    <div data-testid="brief-mindmap">{markdown}</div>
  ),
}))

const markdown = `# 视频标题

## 一句话结论
这是一段用于快速判断教程价值的内容。

## 是否值得看
评分：8.6/10
适合：准备复习的人
不适合：寻找安装步骤的人

## 核心摘要
- 第一点摘要。
- 第二点摘要。

## 章节
- [00:12] 第一章节：开场说明。
- [01:05] 第二章节：关键方法。

## 术语
- 时间锚点：回到原视频指定秒数。

## 行动清单
1. 只看评分最高的章节。
`

describe('BriefResult', () => {
  it('renders the verdict, summary, and timestamped chapter links', () => {
    const document = parseBriefMarkdown(markdown)
    render(
      <BriefResult
        title="视频标题"
        videoUrl="https://www.bilibili.com/video/BV1xx411c7mD"
        document={document}
        onBack={vi.fn()}
        onExportMarkdown={vi.fn()}
      />,
    )

    expect(screen.getByText('这是一段用于快速判断教程价值的内容。')).toBeVisible()
    expect(screen.getByText('8.6')).toBeVisible()
    expect(screen.getByText('第一点摘要。')).toBeVisible()

    fireEvent.click(screen.getByRole('tab', { name: '章节' }))

    const link = screen.getByRole('link', { name: /第一章节/ })
    expect(link).toHaveAttribute(
      'href',
      'https://www.bilibili.com/video/BV1xx411c7mD?t=12',
    )
  })

  it('switches to the mind map and hides absent optional sections', () => {
    const document = parseBriefMarkdown(`# 视频标题

## 一句话结论
只有核心结论，没有术语和行动清单。`)

    render(
      <BriefResult
        title="视频标题"
        videoUrl="https://www.bilibili.com/video/BV1xx411c7mD"
        document={document}
        onBack={vi.fn()}
        onExportMarkdown={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('tab', { name: '思维导图' }))

    expect(screen.getByTestId('brief-mindmap')).toBeVisible()
    expect(screen.queryByText('术语')).not.toBeInTheDocument()
    expect(screen.queryByText('行动清单')).not.toBeInTheDocument()
  })
})
