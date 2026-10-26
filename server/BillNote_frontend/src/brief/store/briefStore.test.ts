import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createBriefStore } from './briefStore'
import type { BriefTask } from '../types'
import type { StateStorage } from 'zustand/middleware'

function makeTask(id: string): BriefTask {
  return {
    id,
    videoUrl: `https://www.bilibili.com/video/${id}`,
    platform: 'bilibili',
    status: 'PENDING',
    message: '任务排队中',
    createdAt: '2026-10-23T10:00:00.000Z',
    updatedAt: '2026-10-23T10:00:00.000Z',
    formData: {
      modelName: 'deepseek-chat',
      providerId: 'deepseek',
      quality: 'medium',
      style: 'brief',
    },
  }
}

describe('briefStore', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('inserts a pending task at the top and selects it', () => {
    const store = createBriefStore(localStorage, 'brief-test-add')
    store.getState().addTask(makeTask('BV1xx411c7mD'))

    expect(store.getState().tasks[0].id).toBe('BV1xx411c7mD')
    expect(store.getState().currentTaskId).toBe('BV1xx411c7mD')
  })

  it('stores Markdown when a task succeeds', () => {
    const store = createBriefStore(localStorage, 'brief-test-success')
    store.getState().addTask(makeTask('BV1xx411c7mD'))

    store.getState().applyTaskStatus('BV1xx411c7mD', {
      status: 'SUCCESS',
      markdown: '# 视频标题\n\n## 一句话结论\n结论。',
      audioMeta: {
        title: '视频标题',
        duration: 120,
        cover_url: 'https://example.com/cover.jpg',
        platform: 'bilibili',
        video_id: 'BV1xx411c7mD',
      },
    })

    expect(store.getState().tasks[0]).toMatchObject({
      status: 'SUCCESS',
      markdown: '# 视频标题\n\n## 一句话结论\n结论。',
      audioMeta: { title: '视频标题' },
    })
  })

  it('retains failed tasks for retry', () => {
    const store = createBriefStore(localStorage, 'brief-test-fail')
    store.getState().addTask(makeTask('BV1xx411c7mD'))

    store.getState().applyTaskStatus('BV1xx411c7mD', {
      status: 'FAILED',
      message: '视频没有可用字幕',
    })

    expect(store.getState().tasks[0]).toMatchObject({
      id: 'BV1xx411c7mD',
      status: 'FAILED',
      message: '视频没有可用字幕',
    })
  })

  it('clears currentTaskId when the selected task is removed', () => {
    const store = createBriefStore(localStorage, 'brief-test-remove')
    store.getState().addTask(makeTask('BV1xx411c7mD'))

    store.getState().removeTask('BV1xx411c7mD')

    expect(store.getState().tasks).toEqual([])
    expect(store.getState().currentTaskId).toBeNull()
  })

  it('exposes hydration state for asynchronous IndexedDB storage', async () => {
    const task = makeTask('BV1xx411c7mD')
    const persisted = JSON.stringify({
      state: { tasks: [task], currentTaskId: task.id },
      version: 0,
    })
    const storage: StateStorage = {
      getItem: async () => persisted,
      setItem: async () => undefined,
      removeItem: async () => undefined,
    }
    const store = createBriefStore(storage, 'brief-test-hydration')

    await vi.waitFor(() => {
      expect(store.getState().hydrated).toBe(true)
    })
    expect(store.getState().tasks[0].id).toBe('BV1xx411c7mD')
  })
})
