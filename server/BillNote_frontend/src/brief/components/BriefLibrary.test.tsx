import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefLibrary } from './BriefLibrary'
import { parseBriefMarkdown } from '../lib/parseBriefMarkdown'
import type { BriefTask } from '../types'

const now = '2026-10-23T10:00:00.000Z'

const tasks: BriefTask[] = [
  {
    id: 'old',
    videoUrl: 'https://www.bilibili.com/video/BV1xx411c7mD',
    platform: 'bilibili',
    status: 'SUCCESS',
    message: '',
    createdAt: '2026-10-21T10:00:00.000Z',
    updatedAt: '2026-10-21T10:00:00.000Z',
    formData: {
      modelName: 'deepseek-chat',
      providerId: 'deepseek',
      quality: 'medium',
      style: 'brief',
    },
    audioMeta: {
      title: '系统设计缓存教程',
      duration: 600,
      cover_url: '',
      platform: 'bilibili',
      video_id: 'BV1xx411c7mD',
    },
    markdown: `## 一句话结论
缓存应该分层设计。`,
    document: parseBriefMarkdown(`## 一句话结论
缓存应该分层设计。`),
  },
  {
    id: 'new',
    videoUrl: 'https://www.bilibili.com/video/BV1xx411c7mD',
    platform: 'bilibili',
    status: 'FAILED',
    message: '没有字幕',
    createdAt: now,
    updatedAt: now,
    formData: {
      modelName: 'deepseek-chat',
      providerId: 'deepseek',
      quality: 'medium',
      style: 'brief',
    },
    audioMeta: {
      title: '产品经理入门',
      duration: 300,
      cover_url: '',
      platform: 'bilibili',
      video_id: 'BV1xx411c7mD',
    },
  },
]

describe('BriefLibrary', () => {
  it('shows newest tasks first with distinct pending and failed labels', () => {
    render(
      <BriefLibrary
        tasks={[
          ...tasks,
          {
            ...tasks[0],
            id: 'pending',
            status: 'PENDING',
            createdAt: '2026-10-22T10:00:00.000Z',
            audioMeta: { ...tasks[0].audioMeta!, title: '处理中的视频' },
          },
        ]}
        onOpenTask={vi.fn()}
      />,
    )

    const titles = screen.getAllByTestId('brief-library-title').map((node) => node.textContent)
    expect(titles).toEqual(['产品经理入门', '处理中的视频', '系统设计缓存教程'])
    expect(screen.getByText('上次失败')).toBeVisible()
    expect(screen.getByText('处理中')).toBeVisible()
  })

  it('searches title and extracted one-line conclusion', () => {
    render(<BriefLibrary tasks={tasks} onOpenTask={vi.fn()} />)

    fireEvent.change(screen.getByRole('searchbox', { name: '搜索视频资料库' }), {
      target: { value: '缓存' },
    })

    expect(screen.getByText('系统设计缓存教程')).toBeVisible()
    expect(screen.queryByText('产品经理入门')).not.toBeInTheDocument()
  })
})
