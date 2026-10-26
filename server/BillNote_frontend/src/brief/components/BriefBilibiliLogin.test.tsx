import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BriefBilibiliLogin } from './BriefBilibiliLogin'

describe('BriefBilibiliLogin', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the QR image and advances from scanned to success', async () => {
    vi.useFakeTimers()
    const onAccountChange = vi.fn()
    const api = {
      start: vi.fn().mockResolvedValue({
        session_id: 'session-1',
        qr_url: 'https://www.bilibili.com/login-qr',
        expires_in: 180,
      }),
      poll: vi
        .fn()
        .mockResolvedValueOnce({
          status: 'scanned',
          message: '已扫码，请在手机中确认',
        })
        .mockResolvedValueOnce({
          status: 'success',
          message: '登录成功',
          account: { logged_in: true, uname: '测试用户', face: '' },
        }),
      status: vi.fn().mockResolvedValue({ logged_in: false }),
      importBrowser: vi.fn(),
      logout: vi.fn(),
    }

    render(
      <BriefBilibiliLogin
        api={api}
        initialAccount={{ logged_in: false }}
        pollIntervalMs={1000}
        onAccountChange={onAccountChange}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '扫码登录 B 站' }))
      await Promise.resolve()
    })
    expect(screen.getByTestId('bilibili-login-qr')).toBeVisible()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByText('已扫码，请在手机中确认')).toBeVisible()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByText('已登录：测试用户')).toBeVisible()
    expect(onAccountChange).toHaveBeenCalledWith({
      logged_in: true,
      uname: '测试用户',
      face: '',
    })
  })

  it('imports Edge cookies without exposing them in the UI', async () => {
    const onAccountChange = vi.fn()
    const api = {
      start: vi.fn(),
      poll: vi.fn(),
      status: vi.fn(),
      importBrowser: vi.fn().mockResolvedValue({
        logged_in: true,
        uname: '浏览器账号',
        face: '',
      }),
      logout: vi.fn(),
    }

    render(
      <BriefBilibiliLogin
        api={api}
        initialAccount={{ logged_in: false }}
        onAccountChange={onAccountChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '从 Edge 导入' }))

    expect(await screen.findByText('已登录：浏览器账号')).toBeVisible()
    expect(screen.queryByText(/SESSDATA/)).not.toBeInTheDocument()
  })
})
