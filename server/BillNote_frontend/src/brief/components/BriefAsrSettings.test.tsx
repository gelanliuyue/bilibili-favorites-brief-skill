import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefAsrSettings } from './BriefAsrSettings'

describe('BriefAsrSettings', () => {
  it('lets the user choose subtitle-only and online ASR modes', async () => {
    const onChange = vi.fn().mockResolvedValue(undefined)
    render(
      <BriefAsrSettings
        initialMode="subtitle_only"
        onChange={onChange}
      />,
    )

    expect(screen.getByText(/云端 ASR 会上传音频/)).toBeVisible()
    fireEvent.click(screen.getByRole('radio', { name: /必剪在线转写/ }))

    expect(onChange).toHaveBeenCalledWith('bcut')
    expect(screen.getByRole('radio', { name: /必剪在线转写/ })).toBeChecked()
  })

  it('shows the local model option as unavailable', () => {
    render(
      <BriefAsrSettings
        initialMode="subtitle_only"
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByText(/本地 Whisper 未启用/)).toBeVisible()
  })
})
