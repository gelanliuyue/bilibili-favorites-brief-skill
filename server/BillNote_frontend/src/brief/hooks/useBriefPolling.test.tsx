import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBriefPolling } from './useBriefPolling'

describe('useBriefPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stops after a terminal success status', async () => {
    const getStatus = vi.fn().mockResolvedValue({
      status: 'SUCCESS',
      task_id: 'task-1',
      result: { markdown: '# done' },
    })
    const onUpdate = vi.fn()

    renderHook(() =>
      useBriefPolling({
        taskId: 'task-1',
        active: true,
        getStatus,
        onUpdate,
        intervalMs: 3000,
      }),
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(getStatus).toHaveBeenCalledTimes(1)
    expect(onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'SUCCESS' }),
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000)
    })
    expect(getStatus).toHaveBeenCalledTimes(1)
  })

  it('keeps polling after a transient request failure', async () => {
    const getStatus = vi
      .fn()
      .mockRejectedValueOnce(new Error('temporary network error'))
      .mockResolvedValue({ status: 'SUMMARIZING', task_id: 'task-1' })
    const onUpdate = vi.fn()

    renderHook(() =>
      useBriefPolling({
        taskId: 'task-1',
        active: true,
        getStatus,
        onUpdate,
        intervalMs: 3000,
      }),
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(getStatus).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(getStatus).toHaveBeenCalledTimes(2)
    expect(onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'SUMMARIZING' }),
    )
  })

  it('cleans up the timer on unmount', async () => {
    const getStatus = vi.fn().mockResolvedValue({
      status: 'SUMMARIZING',
      task_id: 'task-1',
    })
    const view = renderHook(() =>
      useBriefPolling({
        taskId: 'task-1',
        active: true,
        getStatus,
        onUpdate: vi.fn(),
        intervalMs: 3000,
      }),
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    view.unmount()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000)
    })
    expect(getStatus).toHaveBeenCalledTimes(1)
  })
})
