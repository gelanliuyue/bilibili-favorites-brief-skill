import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BriefShell } from './BriefShell'

describe('BriefShell', () => {
  it('exposes exactly the three primary mobile destinations', () => {
    render(
      <BriefShell active="home" onNavigate={vi.fn()}>
        <div>页面内容</div>
      </BriefShell>,
    )

    expect(screen.getByRole('button', { name: '新建' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '资料库' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '设置' })).toBeInTheDocument()
    expect(screen.getByText('页面内容')).toBeInTheDocument()
  })
})
