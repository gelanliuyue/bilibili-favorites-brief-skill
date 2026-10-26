import { useEffect, useRef } from 'react'
import type { BriefTaskResult } from '../types'

interface UseBriefPollingOptions {
  taskId: string | null
  active: boolean
  getStatus: (taskId: string) => Promise<BriefTaskResult>
  onUpdate: (result: BriefTaskResult) => void
  onError?: (error: unknown) => void
  intervalMs?: number
}

export function useBriefPolling({
  taskId,
  active,
  getStatus,
  onUpdate,
  onError,
  intervalMs = 3000,
}: UseBriefPollingOptions) {
  const getStatusRef = useRef(getStatus)
  const onUpdateRef = useRef(onUpdate)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    getStatusRef.current = getStatus
  }, [getStatus])

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    if (!active || !taskId) return

    let stopped = false
    let running = false
    let timer: ReturnType<typeof setInterval> | undefined

    const poll = async () => {
      if (stopped || running) return
      running = true
      try {
        const result = await getStatusRef.current(taskId)
        if (stopped) return
        onUpdateRef.current(result)
        if (result.status === 'SUCCESS' || result.status === 'FAILED') {
          stopped = true
          if (timer) clearInterval(timer)
        }
      } catch (error) {
        if (!stopped) onErrorRef.current?.(error)
      } finally {
        running = false
      }
    }

    void poll()
    timer = setInterval(() => {
      void poll()
    }, intervalMs)

    return () => {
      stopped = true
      if (timer) clearInterval(timer)
    }
  }, [active, intervalMs, taskId])
}
