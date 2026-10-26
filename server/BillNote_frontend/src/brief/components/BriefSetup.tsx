import { useState, type FormEvent } from 'react'
import {
  Activity,
  Cookie,
  KeyRound,
  Save,
  ShieldCheck,
} from 'lucide-react'
import type {
  AsrMode,
  BilibiliAccount,
  BriefProvider,
} from '../types'
import { BriefAsrSettings } from './BriefAsrSettings'
import { BriefBilibiliLogin } from './BriefBilibiliLogin'

interface BriefSetupProps {
  providers: BriefProvider[]
  initialProviderId?: string
  savedKeyHint?: string
  cookieConfigured?: boolean
  bilibiliAccount?: BilibiliAccount
  asrMode?: AsrMode
  onSaveKey: (payload: { providerId: string; apiKey: string }) => void | Promise<void>
  onTestConnection: (payload: { providerId: string }) => void | Promise<void>
  onSaveCookie: (cookie: string) => void | Promise<void>
  onBilibiliAccountChange?: (account: BilibiliAccount) => void
  onAsrModeChange?: (mode: AsrMode) => void | Promise<void>
}

function providerLabel(provider: BriefProvider): string {
  return provider.id === 'qwen' || provider.name.toLowerCase() === 'qwen'
    ? '千问'
    : provider.name
}

export function BriefSetup({
  providers,
  initialProviderId,
  savedKeyHint,
  cookieConfigured = false,
  bilibiliAccount,
  asrMode = 'subtitle_only',
  onSaveKey,
  onTestConnection,
  onSaveCookie,
  onBilibiliAccountChange,
  onAsrModeChange,
}: BriefSetupProps) {
  const [providerId, setProviderId] = useState(
    initialProviderId ?? providers[0]?.id ?? 'deepseek',
  )
  const [apiKey, setApiKey] = useState('')
  const [cookie, setCookie] = useState('')

  const saveKey = async (event: FormEvent) => {
    event.preventDefault()
    if (!apiKey.trim()) return
    await onSaveKey({ providerId, apiKey: apiKey.trim() })
    setApiKey('')
  }

  const saveCookie = async (event: FormEvent) => {
    event.preventDefault()
    if (!cookie.trim()) return
    await onSaveCookie(cookie.trim())
    setCookie('')
  }

  return (
    <section className="brief-page" aria-labelledby="brief-setup-title">
      <header className="brief-page__header">
        <p className="brief-eyebrow">一次性配置</p>
        <h1 id="brief-setup-title" className="brief-page__title">
          连接你的模型和 B 站
        </h1>
        <p className="brief-page__subtitle">
          API Key 与 Cookie 只提交给本机后端，不写进浏览器任务记录。
        </p>
      </header>

      <div className="brief-panel">
        <div className="brief-panel__heading">
          <KeyRound size={17} aria-hidden="true" />
          <h2>摘要模型</h2>
        </div>

        <div className="brief-provider-grid" aria-label="选择模型供应商">
          {providers.map((provider) => {
            const selected = providerId === provider.id
            return (
              <button
                key={provider.id}
                type="button"
                className={`brief-provider${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                onClick={() => setProviderId(provider.id)}
              >
                {providerLabel(provider)}
              </button>
            )
          })}
        </div>

        {savedKeyHint ? (
          <p className="brief-key-state" aria-label="已保存的 API Key">
            <ShieldCheck size={15} aria-hidden="true" />
            {savedKeyHint}
          </p>
        ) : null}

        <form className="brief-form" onSubmit={saveKey}>
          <label className="brief-field">
            <span>API Key</span>
            <input
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="输入新的 API Key"
            />
          </label>
          <div className="brief-form__actions">
            <button className="brief-button brief-button--primary" type="submit">
              <Save size={16} aria-hidden="true" />
              保存模型配置
            </button>
            <button
              className="brief-button"
              type="button"
              onClick={() => void onTestConnection({ providerId })}
            >
              <Activity size={16} aria-hidden="true" />
              测试连接
            </button>
          </div>
        </form>
      </div>

      <div className="brief-panel">
        <div className="brief-panel__heading">
          <Cookie size={17} aria-hidden="true" />
          <h2>B 站登录</h2>
        </div>
        <p className="brief-panel__copy">
          主方案是手机扫码。Cookie 导入仅用于服务和桌面浏览器在同一台电脑的情况。
        </p>
        <BriefBilibiliLogin
          initialAccount={
            bilibiliAccount ?? { logged_in: cookieConfigured }
          }
          onAccountChange={onBilibiliAccountChange}
        />
        <details className="brief-advanced-cookie">
          <summary>高级：手动粘贴 Cookie</summary>
          <form className="brief-form" onSubmit={saveCookie}>
            <label className="brief-field">
              <span>Bilibili Cookie</span>
              <textarea
                rows={3}
                value={cookie}
                onChange={(event) => setCookie(event.target.value)}
                placeholder="SESSDATA=..."
              />
            </label>
            <button className="brief-button" type="submit">
              <Save size={16} aria-hidden="true" />
              保存 B 站 Cookie
            </button>
          </form>
        </details>
      </div>

      <BriefAsrSettings
        initialMode={asrMode}
        onChange={onAsrModeChange ?? (() => undefined)}
      />
    </section>
  )
}
