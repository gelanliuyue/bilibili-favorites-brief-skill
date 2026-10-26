import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefSetup } from './BriefSetup'

describe('BriefSetup', () => {
  it('switches provider and never shows a saved full API key', () => {
    render(
      <BriefSetup
        providers={[
          { id: 'deepseek', name: 'DeepSeek', base_url: 'https://api.deepseek.com', type: 'built-in' },
          { id: 'qwen', name: 'Qwen', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', type: 'built-in' },
        ]}
        savedKeyHint="已保存 ·•••• 0000"
        onSaveKey={vi.fn()}
        onTestConnection={vi.fn()}
        onSaveCookie={vi.fn()}
      />,
    )

    expect(screen.queryByText(/sk-test-placeholder/i)).not.toBeInTheDocument()
    expect(screen.getByText('已保存 ·•••• 0000')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '千问' }))

    expect(screen.getByRole('button', { name: '千问' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'DeepSeek' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('provides accessible save and connection controls', () => {
    render(
      <BriefSetup
        providers={[
          { id: 'deepseek', name: 'DeepSeek', base_url: 'https://api.deepseek.com', type: 'built-in' },
        ]}
        onSaveKey={vi.fn()}
        onTestConnection={vi.fn()}
        onSaveCookie={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: '保存模型配置' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '测试连接' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存 B 站 Cookie' })).toBeInTheDocument()
  })

  it('clears API key and Cookie text after the parent saves them', async () => {
    const onSaveKey = vi.fn().mockResolvedValue(undefined)
    const onSaveCookie = vi.fn().mockResolvedValue(undefined)
    render(
      <BriefSetup
        providers={[
          { id: 'deepseek', name: 'DeepSeek', base_url: 'https://api.deepseek.com', type: 'built-in' },
        ]}
        onSaveKey={onSaveKey}
        onTestConnection={vi.fn()}
        onSaveCookie={onSaveCookie}
      />,
    )

    fireEvent.change(screen.getByLabelText('API Key'), {
      target: { value: 'sk-test-placeholder-0000' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存模型配置' }))
    await vi.waitFor(() => {
      expect(screen.getByLabelText('API Key')).toHaveValue('')
    })

    fireEvent.change(screen.getByLabelText('Bilibili Cookie'), {
      target: { value: 'SESSDATA=secret' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存 B 站 Cookie' }))
    await vi.waitFor(() => {
      expect(screen.getByLabelText('Bilibili Cookie')).toHaveValue('')
    })
  })

  it('integrates QR login and cloud ASR mode controls', () => {
    render(
      <BriefSetup
        providers={[
          { id: 'deepseek', name: 'DeepSeek', base_url: 'https://api.deepseek.com', type: 'built-in' },
        ]}
        bilibiliAccount={{ logged_in: false }}
        asrMode="subtitle_only"
        onSaveKey={vi.fn()}
        onTestConnection={vi.fn()}
        onSaveCookie={vi.fn()}
        onBilibiliAccountChange={vi.fn()}
        onAsrModeChange={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: '扫码登录 B 站' })).toBeVisible()
    expect(screen.getByRole('radio', { name: /仅处理有字幕视频/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /必剪在线转写/ })).not.toBeChecked()
  })
})
