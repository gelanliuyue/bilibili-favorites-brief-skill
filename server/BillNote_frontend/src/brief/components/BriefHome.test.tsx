import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefHome } from './BriefHome'

const provider = {
  id: 'deepseek',
  name: 'DeepSeek',
  base_url: 'https://api.deepseek.com',
  type: 'built-in',
}
const model = { model_name: 'deepseek-chat' }

describe('BriefHome', () => {
  it('rejects a blank URL before submission', async () => {
    const submit = vi.fn()
    render(
      <BriefHome
        provider={provider}
        model={model}
        recentTasks={[]}
        onSubmit={submit}
        onOpenSettings={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '开始拆解' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请输入 B 站链接')
    expect(submit).not.toHaveBeenCalled()
  })

  it('rejects unsupported URLs', async () => {
    const submit = vi.fn()
    render(
      <BriefHome
        provider={provider}
        model={model}
        recentTasks={[]}
        onSubmit={submit}
        onOpenSettings={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('B 站视频链接'), {
      target: { value: 'https://example.com/video/123' },
    })
    fireEvent.click(screen.getByRole('button', { name: '开始拆解' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '目前只支持 B 站视频链接',
    )
    expect(submit).not.toHaveBeenCalled()
  })

  it('requires a configured provider and model', async () => {
    const submit = vi.fn()
    render(
      <BriefHome
        recentTasks={[]}
        onSubmit={submit}
        onOpenSettings={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('B 站视频链接'), {
      target: { value: 'BV1xx411c7mD' },
    })
    fireEvent.click(screen.getByRole('button', { name: '开始拆解' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '请先完成模型配置',
    )
    expect(submit).not.toHaveBeenCalled()
  })

  it('submits a normalized Bilibili URL with the selected model', async () => {
    const submit = vi.fn().mockResolvedValue({ task_id: 'task-1' })
    render(
      <BriefHome
        provider={provider}
        model={model}
        recentTasks={[]}
        onSubmit={submit}
        onOpenSettings={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('B 站视频链接'), {
      target: { value: 'BV1xx411c7mD' },
    })
    fireEvent.click(screen.getByRole('button', { name: '开始拆解' }))

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith({
        videoUrl: 'https://www.bilibili.com/video/BV1xx411c7mD',
        providerId: 'deepseek',
        modelName: 'deepseek-chat',
      })
    })
  })

  it('shows the backend business error message when present', async () => {
    const submit = vi.fn().mockRejectedValue({
      code: 401,
      msg: '模型余额不足，请充值后重试',
      data: null,
    })
    render(
      <BriefHome
        provider={provider}
        model={model}
        recentTasks={[]}
        onSubmit={submit}
        onOpenSettings={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('B 站视频链接'), {
      target: { value: 'BV1xx411c7mD' },
    })
    fireEvent.click(screen.getByRole('button', { name: '开始拆解' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('模型余额不足')
  })
})
