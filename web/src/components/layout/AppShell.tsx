import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const NAV = [
  { to: '/', label: '总览', end: true },
  { to: '/schedule', label: '赛程' },
  { to: '/groups', label: '小组赛' },
  { to: '/bracket', label: '淘汰赛' },
  { to: '/trends', label: '概率演变' },
  { to: '/history', label: '历史' },
  { to: '/model', label: '模型' },
]

function SunIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" />
    </svg>
  )
}

export default function AppShell() {
  const [dark, setDark] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark'),
  )
  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      /* 隐私模式下 localStorage 不可用，忽略 */
    }
  }

  // 窄屏导航横向滚动时，切页后把当前项滚到可见处（兼作"可滚动"的提示，无需渐变遮罩）
  const navRef = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  useEffect(() => {
    navRef.current
      ?.querySelector('[aria-current="page"]')
      ?.scrollIntoView({ inline: 'center', block: 'nearest' })
  }, [pathname])

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3">
          <NavLink to="/" className="shrink-0 text-md font-medium">
            2026 世界杯预测
          </NavLink>
          <div className="flex min-w-0 items-center gap-1">
            {/* 窄屏导航横向滚动（隐藏滚动条），不再换行/溢出 */}
            <nav
              ref={navRef}
              className="flex min-w-0 gap-1 overflow-x-auto text-sm [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    `shrink-0 whitespace-nowrap rounded-lg px-2 py-1 transition-colors ${
                      isActive
                        ? 'bg-accent-soft text-accent'
                        : 'text-ink-secondary hover:bg-surface'
                    }`
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </nav>
            <button
              onClick={toggleTheme}
              aria-label={dark ? '切换到浅色模式' : '切换到深色模式'}
              className="ml-1 shrink-0 rounded-lg p-1.5 text-ink-secondary transition-colors hover:bg-surface hover:text-ink"
            >
              {dark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
