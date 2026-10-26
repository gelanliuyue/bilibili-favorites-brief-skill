import { useState, type FormEvent } from 'react'
import {
  BookOpenCheck,
  Link2,
  LoaderCircle,
  Settings2,
  WandSparkles,
} from 'lucide-react'
import { normalizeBilibiliInput } from '../lib/bilibiliUrl'
import type {
  BriefModel,
  BriefProvider,
  BriefTask,
} from '../types'

interface BriefHomeProps {
  provider?: BriefProvider
  model?: BriefModel
  recentTasks: BriefTask[]
  onSubmit: (input: {
    videoUrl: string
    providerId: string
    modelName: string
  }) => Promise<{ task_id: string }>
  onOpenSettings: () => void
  onOpenTask?: (taskId: string) => void
  onTaskCreated?: (taskId: string) => void
}

export function toBriefSubmissionError(error: unknown): string {
  const candidate = error as {
    message?: string
    data?: {
      reason?: string
      subtitle_checked?: boolean
    }
    msg?: string
    response?: {
      status?: number
    }
  }

  if (candidate?.data?.reason === 'transcriber_model_not_ready') {
    return candidate.data.subtitle_checked
      ? '这个视频没有可用字幕。请配置云端语音识别，或换一个有字幕的视频。'
      : '没有可用字幕，而且语音识别服务尚未就绪。请先完成语音识别配置。'
  }

  const status = candidate?.response?.status
  if (status === 401 || status === 403) {
    return 'API Key 或 B 站登录状态已失效，请到设置中重新检查。'
  }

  if (candidate?.message?.toLowerCase().includes('network')) {
    return '网络请求失败，请检查本机后端和网络连接。'
  }

  return candidate?.msg || candidate?.message || '任务提交失败，请稍后重试。'
}

export function BriefHome({
  provider,
  model,
  recentTasks,
  onSubmit,
  onOpenSettings,
  onOpenTask,
  onTaskCreated,
}: BriefHomeProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    const normalized = normalizeBilibiliInput(input)
    if (!normalized.url) {
      setError(
        input.trim()
          ? '目前只支持 B 站视频链接、b23.tv 短链或 BV 号。'
          : '请输入 B 站链接。',
      )
      return
    }

    if (!provider || !model?.model_name) {
      setError('请先完成模型配置，再开始拆解视频。')
      return
    }

    setSubmitting(true)
    try {
      const task = await onSubmit({
        videoUrl: normalized.url,
        providerId: provider.id,
        modelName: model.model_name,
      })
      onTaskCreated?.(task.task_id)
    } catch (submitError) {
      setError(toBriefSubmissionError(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="brief-page" aria-labelledby="brief-home-title">
      <header className="brief-page__header">
        <h1 id="brief-home-title" className="brief-page__title">
          今天想拆解哪个教程？
        </h1>
        <p className="brief-page__subtitle">
          先判断值不值得看，再看懂结构，最后决定从哪一段开始。
        </p>
      </header>

      <form className="brief-link-form" onSubmit={submit}>
        <label className="brief-link-box">
          <Link2 size={18} aria-hidden="true" />
          <span className="sr-only">B 站视频链接</span>
          <input
            aria-label="B 站视频链接"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="粘贴 B 站链接或 BV 号"
            autoComplete="off"
          />
        </label>
        <button
          type="submit"
          className="brief-button brief-button--primary brief-submit"
          disabled={submitting}
        >
          {submitting ? (
            <LoaderCircle size={17} className="brief-spin" aria-hidden="true" />
          ) : (
            <WandSparkles size={17} aria-hidden="true" />
          )}
          {submitting ? '正在提交…' : '开始拆解'}
        </button>
      </form>

      {error ? (
        <div className="brief-error" role="alert">
          <span>{error}</span>
          {error.includes('配置') ? (
            <button type="button" onClick={onOpenSettings}>
              <Settings2 size={15} aria-hidden="true" />
              去设置
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="brief-section-heading">
        <h2>最近处理</h2>
        {recentTasks.length ? <span>{recentTasks.length} 条</span> : null}
      </div>

      {recentTasks.length ? (
        <div className="brief-recent-list">
          {recentTasks.slice(0, 3).map((task) => (
            <button
              key={task.id}
              type="button"
              className="brief-recent"
              onClick={() => onOpenTask?.(task.id)}
            >
              <span className="brief-recent__icon" aria-hidden="true">
                <BookOpenCheck size={19} />
              </span>
              <span className="brief-recent__body">
                <strong>{task.audioMeta?.title || task.videoUrl}</strong>
                <small>
                  {task.status === 'SUCCESS'
                    ? '已生成'
                    : task.status === 'FAILED'
                      ? '上次失败，可重新处理'
                      : '处理中'}
                </small>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="brief-empty">
          <BookOpenCheck size={24} aria-hidden="true" />
          <p>还没有拆解记录。先从一个收藏很久的教程开始。</p>
        </div>
      )}
    </section>
  )
}
