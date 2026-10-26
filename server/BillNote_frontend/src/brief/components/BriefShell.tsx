import type { ReactNode } from 'react'
import {
  Library,
  Settings2,
  Sparkles,
  SquarePen,
} from 'lucide-react'
import '../styles/brief.css'

export type BriefDestination = 'home' | 'library' | 'settings'

interface BriefShellProps {
  active: BriefDestination
  loggedIn?: boolean
  children: ReactNode
  onNavigate: (destination: BriefDestination) => void
}

const destinations: Array<{
  id: BriefDestination
  label: string
  icon: typeof SquarePen
}> = [
  { id: 'home', label: '新建', icon: SquarePen },
  { id: 'library', label: '资料库', icon: Library },
  { id: 'settings', label: '设置', icon: Settings2 },
]

export function BriefShell({
  active,
  loggedIn = false,
  children,
  onNavigate,
}: BriefShellProps) {
  return (
    <div className="brief-app">
      <div className="brief-app__frame">
        <header className="brief-topbar">
          <div className="brief-brand">
            <span className="brief-brand__mark" aria-hidden="true">
              <Sparkles size={17} />
            </span>
            <span>BiliBrief</span>
          </div>
          <span className="brief-login-status">
            <span
              className={
                loggedIn
                  ? 'brief-login-status__dot is-ready'
                  : 'brief-login-status__dot'
              }
            />
            {loggedIn ? 'B 站已登录' : 'B 站未登录'}
          </span>
        </header>

        <main className="brief-main">{children}</main>

        <nav className="brief-bottom-nav" aria-label="主导航">
          {destinations.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`brief-bottom-nav__item${active === id ? ' is-active' : ''}`}
              aria-current={active === id ? 'page' : undefined}
              onClick={() => onNavigate(id)}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  )
}
