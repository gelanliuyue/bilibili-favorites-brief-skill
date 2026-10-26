import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  Chrome,
  LogOut,
  QrCode,
  RotateCcw,
  ScanLine,
} from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import {
  getBilibiliStatus,
  importBilibiliBrowser,
  logoutBilibili,
  pollBilibiliQr,
  startBilibiliQr,
} from '../services/briefApi'
import type {
  BilibiliAccount,
  BilibiliQrPoll,
  BilibiliQrStart,
} from '../types'

export interface BilibiliLoginApi {
  start: () => Promise<BilibiliQrStart>
  poll: (sessionId: string) => Promise<BilibiliQrPoll>
  status: () => Promise<BilibiliAccount>
  importBrowser: (browser: 'edge' | 'chrome') => Promise<BilibiliAccount>
  logout: () => Promise<void>
}

interface BriefBilibiliLoginProps {
  initialAccount?: BilibiliAccount
  api?: BilibiliLoginApi
  pollIntervalMs?: number
  onAccountChange?: (account: BilibiliAccount) => void
  onCookieConfigured?: () => void
}

const defaultApi: BilibiliLoginApi = {
  start: startBilibiliQr,
  poll: pollBilibiliQr,
  status: getBilibiliStatus,
  importBrowser: importBilibiliBrowser,
  logout: logoutBilibili,
}

export function BriefBilibiliLogin({
  initialAccount,
  api = defaultApi,
  pollIntervalMs = 1800,
  onAccountChange,
  onCookieConfigured,
}: BriefBilibiliLoginProps) {
  const [account, setAccount] = useState<BilibiliAccount>(
    initialAccount ?? { logged_in: false },
  )
  const [qr, setQr] = useState<BilibiliQrStart | null>(null)
  const [poll, setPoll] = useState<BilibiliQrPoll | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (initialAccount) return
    void api.status().then(setAccount).catch(() => undefined)
  }, [api, initialAccount])

  useEffect(() => {
    if (!qr || account.logged_in) return
    let stopped = false
    let running = false
    let timer: ReturnType<typeof setInterval> | undefined

    const check = async () => {
      if (stopped || running) return
      running = true
      try {
        const result = await api.poll(qr.session_id)
        if (stopped) return
        setPoll(result)
        if (result.status === 'success' && result.account) {
          setAccount(result.account)
          onAccountChange?.(result.account)
          onCookieConfigured?.()
          stopped = true
          if (timer) clearInterval(timer)
        }
        if (result.status === 'expired' || result.status === 'error') {
          stopped = true
          if (timer) clearInterval(timer)
        }
      } catch (pollError) {
        if (!stopped) {
          setError(
            (pollError as { message?: string })?.message ||
              '查询扫码状态失败，请稍后重试。',
          )
        }
      } finally {
        running = false
      }
    }

    timer = setInterval(() => {
      void check()
    }, pollIntervalMs)

    return () => {
      stopped = true
      if (timer) clearInterval(timer)
    }
  }, [
    account.logged_in,
    api,
    onAccountChange,
    onCookieConfigured,
    pollIntervalMs,
    qr,
  ])

  const start = async () => {
    setBusy(true)
    setError('')
    setPoll(null)
    try {
      setQr(await api.start())
    } catch (startError) {
      setError(
        (startError as { message?: string })?.message ||
          '生成二维码失败，请稍后重试。',
      )
    } finally {
      setBusy(false)
    }
  }

  const importBrowser = async (browser: 'edge' | 'chrome') => {
    setBusy(true)
    setError('')
    try {
      const imported = await api.importBrowser(browser)
      setAccount(imported)
      onAccountChange?.(imported)
      if (imported.logged_in) onCookieConfigured?.()
    } catch (importError) {
      setError(
        (importError as { msg?: string; message?: string })?.msg ||
          (importError as { message?: string })?.message ||
          '浏览器 Cookie 导入失败。',
      )
    } finally {
      setBusy(false)
    }
  }

  const logout = async () => {
    setBusy(true)
    try {
      await api.logout()
      setAccount({ logged_in: false })
      setQr(null)
      setPoll(null)
      onAccountChange?.({ logged_in: false })
    } finally {
      setBusy(false)
    }
  }

  if (account.logged_in) {
    return (
      <div className="brief-bili-login is-connected">
        <span className="brief-bili-login__icon">
          <CheckCircle2 size={19} aria-hidden="true" />
        </span>
        <span>
          <strong>已登录：{account.uname || 'B 站账号'}</strong>
          <small>字幕和需要登录的视频会使用这个账号。</small>
        </span>
        <button type="button" onClick={() => void logout()} disabled={busy}>
          <LogOut size={15} aria-hidden="true" />
          退出
        </button>
      </div>
    )
  }

  return (
    <div className="brief-bili-login">
      <div className="brief-bili-login__heading">
        <QrCode size={18} aria-hidden="true" />
        <div>
          <strong>B 站登录</strong>
          <small>用已经登录的手机 B 站 App 扫码确认。</small>
        </div>
      </div>

      {!qr ? (
        <button
          className="brief-button brief-button--primary"
          type="button"
          onClick={() => void start()}
          disabled={busy}
        >
          <ScanLine size={17} aria-hidden="true" />
          扫码登录 B 站
        </button>
      ) : (
        <div className="brief-qr-area">
          <div className="brief-qr-code" data-testid="bilibili-login-qr">
            <QRCodeSVG value={qr.qr_url} size={176} />
          </div>
          <p>{poll?.message || '请使用哔哩哔哩 App 扫码'}</p>
          {poll?.status === 'expired' || poll?.status === 'error' ? (
            <button className="brief-button" type="button" onClick={() => void start()}>
              <RotateCcw size={16} aria-hidden="true" />
              重新生成二维码
            </button>
          ) : null}
        </div>
      )}

      <div className="brief-browser-import">
        <span>也可以在运行服务的电脑上：</span>
        <button type="button" onClick={() => void importBrowser('edge')} disabled={busy}>
          <Chrome size={15} aria-hidden="true" />
          从 Edge 导入
        </button>
        <button type="button" onClick={() => void importBrowser('chrome')} disabled={busy}>
          <Chrome size={15} aria-hidden="true" />
          从 Chrome 导入
        </button>
      </div>

      {error ? <p className="brief-error" role="alert">{error}</p> : null}
    </div>
  )
}
