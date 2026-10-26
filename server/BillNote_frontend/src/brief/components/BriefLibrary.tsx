import { useMemo, useState } from 'react'
import { BookOpenCheck, Search } from 'lucide-react'
import type { BriefTask } from '../types'

interface BriefLibraryProps {
  tasks: BriefTask[]
  onOpenTask: (taskId: string) => void
}

function taskTitle(task: BriefTask): string {
  return task.audioMeta?.title || task.document?.oneLine || task.videoUrl
}

function taskSearchText(task: BriefTask): string {
  return [
    taskTitle(task),
    task.document?.oneLine,
    ...(task.document?.chapters.map((chapter) => chapter.title) ?? []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function taskStatusLabel(status: BriefTask['status']): string {
  if (status === 'FAILED') return '上次失败'
  if (status === 'SUCCESS') return '已完成'
  return '处理中'
}

export function BriefLibrary({ tasks, onOpenTask }: BriefLibraryProps) {
  const [query, setQuery] = useState('')

  const visibleTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return [...tasks]
      .sort(
        (left, right) =>
          new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
      )
      .filter((task) => !keyword || taskSearchText(task).includes(keyword))
  }, [query, tasks])

  return (
    <section className="brief-page" aria-labelledby="brief-library-title">
      <header className="brief-page__header">
        <h1 id="brief-library-title" className="brief-page__title">
          视频资料库
        </h1>
        <p className="brief-page__subtitle">
          按标题、结论或章节找回以前拆解过的教程。
        </p>
      </header>

      <label className="brief-search">
        <Search size={17} aria-hidden="true" />
        <span className="sr-only">搜索视频资料库</span>
        <input
          type="search"
          role="searchbox"
          aria-label="搜索视频资料库"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索视频资料库"
        />
      </label>

      {visibleTasks.length ? (
        <div className="brief-library-list">
          {visibleTasks.map((task) => (
            <button
              key={task.id}
              type="button"
              className="brief-library-item"
              onClick={() => onOpenTask(task.id)}
            >
              <span className="brief-library-item__icon" aria-hidden="true">
                <BookOpenCheck size={19} />
              </span>
              <span>
                <strong data-testid="brief-library-title">{taskTitle(task)}</strong>
                <small>{task.document?.oneLine || task.message || '暂无摘要'}</small>
              </span>
              <em className={`is-${task.status.toLowerCase()}`}>
                {taskStatusLabel(task.status)}
              </em>
            </button>
          ))}
        </div>
      ) : (
        <div className="brief-empty">
          <BookOpenCheck size={24} aria-hidden="true" />
          <p>{query ? '没有找到匹配的视频。' : '资料库还是空的。'}</p>
        </div>
      )}
    </section>
  )
}
