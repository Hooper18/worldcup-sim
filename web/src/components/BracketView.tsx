import { Link } from 'react-router-dom'
import type { Knockout, Match } from '../types/data'
import { useTeams } from '../hooks/useTeams'
import { pct } from '../lib/format'
import { bracketColumns } from '../lib/bracket'
import Flag from './Flag'

// 自绘对阵树：分 5 列（32强→决赛），未定槽位显示最可能队伍+概率。
// 列顺序按对阵树（bracketColumns）排，使父场次恰好夹在两场上游中间；移动端横向滚动。

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
  bracket,
}: {
  matches: Match[]
  bracket?: Knockout['bracket']
}) {
  const byId = new Map(matches.map((m) => [m.id, m]))
  const columns = bracketColumns(bracket)
  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex min-w-[760px] gap-4">
        {columns.map((col) => (
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
                    className="divide-y divide-line rounded-lg border border-line bg-card/40 transition-colors hover:bg-surface"
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
