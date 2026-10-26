import { describe, expect, it } from 'vitest'
import { describeTaskPresentation } from './lib/taskPresentation'
import { parseBriefMarkdown } from './lib/parseBriefMarkdown'
import type { BriefTask } from './types'

const task: BriefTask = {
  id: 'task-1',
  videoUrl: 'https://www.bilibili.com/video/BV1xx411c7mD',
  platform: 'bilibili',
  status: 'PENDING',
  message: '',
  createdAt: '2026-10-23T10:00:00.000Z',
  updatedAt: '2026-10-23T10:00:00.000Z',
  formData: {
    modelName: 'deepseek-chat',
    providerId: 'deepseek',
    quality: 'medium',
    style: 'brief',
  },
}

describe('task presentation', () => {
  it('waits for asynchronous history hydration before reporting a missing task', () => {
    expect(describeTaskPresentation(undefined, false)).toBe('hydrating')
  })

  it('distinguishes a missing task from an incomplete successful result', () => {
    expect(describeTaskPresentation(undefined, true)).toBe('missing')
    expect(
      describeTaskPresentation({ ...task, status: 'SUCCESS' }, true),
    ).toBe('incomplete')
  })

  it('renders a result only when both Markdown and parsed document exist', () => {
    const markdown = '## 一句话结论\n结论。'
    expect(
      describeTaskPresentation(
        {
          ...task,
          status: 'SUCCESS',
          markdown,
          document: parseBriefMarkdown(markdown),
        },
        true,
      ),
    ).toBe('result')
  })
})
