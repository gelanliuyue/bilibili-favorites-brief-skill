import { useState } from 'react'
import {
  ArrowLeft,
  Download,
  ExternalLink,
  Play,
  Sparkles,
} from 'lucide-react'
import type { BriefDocument } from '../lib/parseBriefMarkdown'
import { BriefMindMap } from './BriefMindMap'

interface BriefResultProps {
  title: string
  videoUrl: string
  document: BriefDocument
  onBack: () => void
  onExportMarkdown: () => void
}

type ResultTab = 'summary' | 'mindmap' | 'chapters'

function videoTimeUrl(videoUrl: string, seconds: number): string {
  try {
    const url = new URL(videoUrl)
    url.searchParams.set('t', String(seconds))
    return url.toString()
  } catch {
    return videoUrl
  }
}

export function BriefResult({
  title,
  videoUrl,
  document,
  onBack,
  onExportMarkdown,
}: BriefResultProps) {
  const [tab, setTab] = useState<ResultTab>('summary')

  return (
    <article className="brief-result">
      <header className="brief-result__header">
        <button
          className="brief-icon-button"
          type="button"
          aria-label="返回首页"
          onClick={onBack}
        >
          <ArrowLeft size={18} aria-hidden="true" />
        </button>
        <div>
          <h1>{title}</h1>
          <p>B 站视频知识卡</p>
        </div>
      </header>

      <section className="brief-verdict">
        <p className="brief-eyebrow">一分钟看懂</p>
        <h2>{document.oneLine || '暂时没有提取到一句话结论'}</h2>
        <div className="brief-verdict__footer">
          <span className="brief-score">
            {document.verdict.score ?? '–'}
            <small>{document.verdict.score === null ? ' 暂无评分' : ' / 10 值得看'}</small>
          </span>
          <span className="brief-audience">
            {document.verdict.audience.length
              ? `适合：${document.verdict.audience.join('、')}`
              : '适合人群：视频未明确说明'}
          </span>
        </div>
      </section>

      <div className="brief-result-tabs" role="tablist" aria-label="结果视图">
        {([
          ['summary', '摘要'],
          ['mindmap', '思维导图'],
          ['chapters', '章节'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={tab === value ? 'is-active' : ''}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="brief-result-panel">
        {tab === 'summary' ? (
          <div className="brief-result-summary">
            {document.summaryItems.length ? (
              <ul>
                {document.summaryItems.map((item) => (
                  <li key={item}>
                    <Sparkles size={15} aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="brief-panel__copy">视频没有提取到更多摘要条目。</p>
            )}

            {document.terms.length ? (
              <section className="brief-result-section">
                <h3>术语</h3>
                <dl>
                  {document.terms.map((item) => (
                    <div key={item.term}>
                      <dt>{item.term}</dt>
                      <dd>{item.explanation}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}

            {document.actions.length ? (
              <section className="brief-result-section">
                <h3>行动清单</h3>
                <ol>
                  {document.actions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </section>
            ) : null}
          </div>
        ) : null}

        {tab === 'mindmap' ? (
          <BriefMindMap markdown={document.rawMarkdown} title={title} />
        ) : null}

        {tab === 'chapters' ? (
          <div className="brief-chapter-list">
            {document.chapters.length ? (
              document.chapters.map((chapter) => (
                <a
                  key={`${chapter.time}-${chapter.title}`}
                  href={videoTimeUrl(videoUrl, chapter.seconds)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span>{chapter.time}</span>
                  <strong>{chapter.title}</strong>
                  <Play size={15} aria-hidden="true" />
                </a>
              ))
            ) : (
              <p className="brief-panel__copy">视频没有提取到可靠的时间章节。</p>
            )}
          </div>
        ) : null}
      </div>

      <div className="brief-result-actions">
        <button className="brief-button" type="button" onClick={onExportMarkdown}>
          <Download size={16} aria-hidden="true" />
          导出 Markdown
        </button>
        <a
          className="brief-button brief-button--primary"
          href={videoUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink size={16} aria-hidden="true" />
          回到原视频
        </a>
      </div>
    </article>
  )
}
