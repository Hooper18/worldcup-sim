import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: '总览', end: true },
  { to: '/schedule', label: '赛程' },
  { to: '/groups', label: '小组赛' },
  { to: '/bracket', label: '淘汰赛' },
  { to: '/trends', label: '概率演变' },
  { to: '/model', label: '模型' },
]

export default function AppShell() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <NavLink to="/" className="text-md font-medium">
            2026 世界杯预测
          </NavLink>
          <nav className="flex gap-1 text-sm">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-lg px-2.5 py-1 transition-colors ${
                    isActive ? 'bg-accent-soft text-accent' : 'text-ink-secondary hover:bg-surface'
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
