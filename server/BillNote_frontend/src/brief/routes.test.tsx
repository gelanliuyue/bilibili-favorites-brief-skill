import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { BriefRoutes } from './routes'

vi.mock('./BriefWorkspace', () => ({
  BriefWorkspace: ({ view }: { view: string }) => (
    <div>Brief workspace: {view}</div>
  ),
}))

vi.mock('@/pages/HomePage/Home.tsx', () => ({
  HomePage: () => <div>BiliNote classic</div>,
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <BriefRoutes />
    </MemoryRouter>,
  )
}

describe('BriefRoutes', () => {
  it('redirects the root route to the mobile brief workspace', () => {
    renderAt('/')
    expect(screen.getByText('Brief workspace: home')).toBeVisible()
  })

  it('routes brief home, setup, and library', () => {
    const { unmount } = renderAt('/brief')
    expect(screen.getByText('Brief workspace: home')).toBeVisible()
    unmount()

    renderAt('/brief/setup')
    expect(screen.getByText('Brief workspace: setup')).toBeVisible()
  })

  it('keeps the original BiliNote interface reachable at classic', () => {
    renderAt('/classic')
    expect(screen.getByText('BiliNote classic')).toBeVisible()
  })
})
