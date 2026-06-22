import { Link } from 'react-router-dom'
import type { Knockout, Match } from '../types/data'
import { useTeams } from '../hooks/useTeams'
import { pct } from '../lib/format'
import Flag from './Flag'

// 自绘对阵树：CSS grid 分 5 列（32强→决赛），未定槽位显示最可能队伍+概率。
// 移动端横向滚动。连接线用极淡边框近似（避免图表库画 bracket 的复杂度）。

const COLUMNS: { stage: string; label: string; ids: number[] }[] = [
  { stage: 'r32', label: '32 强', ids: range(73, 88) },
  { stage: 'r16', label: '16 强', ids: range(89, 96) },
  { stage: 'qf', label: '8 强', ids: range(97, 100) },
  { stage: 'sf', label: '半决赛', ids: [101, 102] },
  { stage: 'final', label: '决赛', ids: [104] },
]

function range(a: number, b: number): number[] {
  return Array.from({ length: b - a + 1 }, (_, i) => a + i)
}

function topSlot(
  m: Match | undefined,
  side: 'home' | 'away',
): { code: string | null; p: number | null } {
  if (!m) return { code: null, p: null }
  const resolved = side === 'home' ? m.home : m.away
  if (m.stage === 'group' || (m.stage === 'r32' && resolved && !/^[123]/.test(resolved))) {
    return { code: resolved, p: null }
  }
  const dist = m.slot_dist?.[side]
  if (dist && dist.length) return { code: dist[0].team, p: dist[0].p }
  return { code: null, p: null }
}

function SlotCell({ code, p }: { code: string | null; p: number | null }) {
  const teams = useTeams()
  const t = code ? teams?.[code] : null
  return (
    <div className="flex items-center justify-between gap-1 px-2 py-1.5">
      <span className="flex items-center gap-1.5 truncate text-sm">
        <Flag code={code} />
        <span className="truncate">{t?.name_zh ?? '待定'}</span>
      </span>
      {p != null && <span className="shrink-0 text-xs tabular-nums text-ink-faint">{pct(p)}</span>}
    </div>
  )
}

export default function BracketView({
  matches,
  knockout,
}: {
  matches: Match[]
  knockout: Knockout
}) {
  void knockout
  const byId = new Map(matches.map((m) => [m.id, m]))
  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex min-w-[760px] gap-4">
        {COLUMNS.map((col) => (
          <div key={col.stage} className="flex flex-1 flex-col">
            <div className="mb-2 text-center text-xs font-medium text-ink-secondary">
              {col.label}
            </div>
            <div className="flex flex-1 flex-col justify-around gap-2">
              {col.ids.map((id) => {
                const m = byId.get(id)
                const home = topSlot(m, 'home')
                const away = topSlot(m, 'away')
                return (
                  <Link
                    key={id}
                    to={`/match/${id}`}
                    className="divide-y divide-line rounded-lg border border-line bg-white/40 transition-colors hover:bg-surface"
                  >
                    <SlotCell code={home.code} p={home.p} />
                    <SlotCell code={away.code} p={away.p} />
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
