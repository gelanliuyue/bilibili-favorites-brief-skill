import { useState } from 'react'
import { Captions, Cloud, Info } from 'lucide-react'
import type { AsrMode } from '../types'

interface BriefAsrSettingsProps {
  initialMode: AsrMode
  onChange: (mode: AsrMode) => void | Promise<void>
}

const options: Array<{
  value: AsrMode
  label: string
  description: string
}> = [
  {
    value: 'subtitle_only',
    label: '仅处理有字幕视频',
    description: '不上传音频；没有字幕时停止。',
  },
  {
    value: 'bcut',
    label: '必剪在线转写',
    description: '通过 B 站必剪服务识别无字幕音频。',
  },
  {
    value: 'kuaishou',
    label: '快手在线转写',
    description: '通过快手在线服务识别无字幕音频。',
  },
  {
    value: 'groq',
    label: 'Groq 语音识别',
    description: '需要先在模型设置中配置 Groq API Key。',
  },
]

export function BriefAsrSettings({
  initialMode,
  onChange,
}: BriefAsrSettingsProps) {
  const [mode, setMode] = useState<AsrMode>(initialMode)

  const choose = (nextMode: AsrMode) => {
    setMode(nextMode)
    void onChange(nextMode)
  }

  return (
    <section className="brief-asr-settings" aria-labelledby="brief-asr-title">
      <div className="brief-bili-login__heading">
        <Captions size={18} aria-hidden="true" />
        <div>
          <strong id="brief-asr-title">无字幕视频</strong>
          <small>有字幕时无需经过语音识别。</small>
        </div>
      </div>

      <div className="brief-asr-options">
        {options.map((option) => (
          <label key={option.value} className="brief-asr-option">
            <input
              type="radio"
              name="brief-asr-mode"
              value={option.value}
              checked={mode === option.value}
              onChange={() => choose(option.value)}
            />
            <span>
              <strong>{option.label}</strong>
              <small>{option.description}</small>
            </span>
          </label>
        ))}
      </div>

      <p className="brief-asr-warning">
        <Cloud size={14} aria-hidden="true" />
        云端 ASR 会上传音频，部分服务可能限流或计费。
      </p>
      <p className="brief-note">
        <Info size={13} aria-hidden="true" /> 本地 Whisper 未启用。DeepSeek 和普通千问文本模型不能转录音频。
      </p>
    </section>
  )
}
