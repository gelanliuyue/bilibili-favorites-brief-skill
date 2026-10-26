import { CircleCheck, LoaderCircle, RotateCcw } from 'lucide-react'
import type { BriefTaskStatus } from '../types'

interface BriefProcessingProps {
  status: BriefTaskStatus
  message?: string
  onRetry?: () => void
}

const stages: Array<{
  statuses: BriefTaskStatus[]
  label: string
}> = [
  { statuses: ['PENDING', 'PARSING'], label: '读取视频信息' },
  { statuses: ['DOWNLOADING'], label: '准备字幕或音频' },
  { statuses: ['TRANSCRIBING'], label: '整理视频文字' },
  { statuses: ['SUMMARIZING'], label: '提炼摘要与章节' },
  { statuses: ['FORMATTING', 'SAVING', 'SUCCESS'], label: '完成并保存' },
]

function currentStageIndex(status: BriefTaskStatus): number {
  return stages.findIndex((stage) => stage.statuses.includes(status))
}

export function BriefProcessing({
  status,
  message,
  onRetry,
}: BriefProcessingProps) {
  if (status === 'FAILED') {
    return (
      <section className="brief-processing brief-processing--failed" role="alert">
        <span className="brief-processing__icon">
          <RotateCcw size={25} aria-hidden="true" />
        </span>
        <h1>这次没有生成成功</h1>
        <p>{message || '任务处理失败，请检查配置后重试。'}</p>
        {onRetry ? (
          <button className="brief-button brief-button--primary" type="button" onClick={onRetry}>
            <RotateCcw size={16} aria-hidden="true" />
            重新处理
          </button>
        ) : null}
      </section>
    )
  }

  const currentIndex = Math.max(0, currentStageIndex(status))
  const progress = Math.min(100, ((currentIndex + 1) / stages.length) * 100)

  return (
    <section className="brief-processing" aria-live="polite">
      <span className="brief-processing__icon">
        <LoaderCircle size={25} className="brief-spin" aria-hidden="true" />
      </span>
      <h1>正在理解这个视频</h1>
      <p>{message || '字幕准备完成后，会提炼重点、章节和思维导图。'}</p>
      <div
        className="brief-progress"
        role="progressbar"
        aria-label="生成进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress)}
      >
        <span style={{ width: `${progress}%` }} />
      </div>
      <ol className="brief-stage-list">
        {stages.map((stage, index) => {
          const state =
            index < currentIndex ? 'is-done' : index === currentIndex ? 'is-active' : ''
          return (
            <li key={stage.label} className={state}>
              <span>{index < currentIndex ? <CircleCheck size={16} /> : index + 1}</span>
              {stage.label}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
