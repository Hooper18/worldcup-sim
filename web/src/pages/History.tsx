import { useMemo, useState } from 'react'
import { useData } from '../hooks/useData'
import { useTeams } from '../hooks/useTeams'
import type { Evolution } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import Flag from '../components/Flag'
import { pct } from '../lib/format'
import { dedupeEvolution } from '../lib/evolution'

// 历史回放：拖动滑块回看任一时点的夺冠概率排名（数据来自 evolution.json 的逐快照时序）。
export default function History() {
  const evo = useData<Evolution>('evolution')
  const teams = useTeams()
  const [idx, setIdx] = useState<number | null>(null)

  const dedup = useMemo(() => (evo.data ? dedupeEvolution(evo.data) : null), [evo.data])

  if (evo.loading) return <Loading />
  if (evo.error || !evo.data || !dedup) return <ErrorMsg msg={evo.error || '无数据'} />

  const { keepIdx, matchesPlayed } = dedup
  const snaps = evo.data.snapshots
  const N = keepIdx.length
  const sel = idx == null ? N - 1 : Math.min(idx, N - 1)
  const snapI = keepIdx[sel]
  const prevI = sel > 0 ? keepIdx[sel - 1] : null
  const snap = snaps[snapI]

  const ranked = Object.entries(evo.data.teams)
    .map(([code, m]) => ({
      code,
      p: m.champion[snapI] ?? 0,
      prev: prevI != null ? (m.champion[prevI] ?? 0) : null,
    }))
    .sort((a, b) => b.p - a.p)
    .slice(0, 12)
  const max = Math.max(...ranked.map((r) => r.p), 0.01)

  const dateLabel = new Date(snap.at).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-medium">历史回放</h1>
        <p className="mt-1 text-xs text-ink-faint">拖动滑块回看夺冠概率随赛事推进的任一时点快照</p>
      </div>

      <Card className="space-y-3 px-4 py-4">
        <div className="flex items-baseline justify-between">
          <span className="text-md font-medium tabular-nums">{snap.matches_played} 场后</span>
          <span className="text-xs text-ink-faint">{dateLabel}</span>
        </div>
        <input
          type="range"
          min={0}
          max={N - 1}
          value={sel}
          onChange={(e) => setIdx(Number(e.target.value))}
          aria-label="选择赛事时点"
          className="w-full"
          style={{ accentColor: 'rgb(var(--c-accent))' }}
        />
        <div className="flex justify-between text-xs text-ink-faint">
          <span>开赛（{matchesPlayed[0]} 场）</span>
          <span>最新（{matchesPlayed[N - 1]} 场）</span>
        </div>
      </Card>

      <section className="space-y-2">
        <h2 className="mb-1 text-sm text-ink-faint">
          该时点夺冠概率 Top 12（箭头为较上一时点变化）
        </h2>
        {ranked.map((r, i) => {
          const delta = r.prev == null ? null : r.p - r.prev
          const up = delta != null && delta > 0.0005
          const down = delta != null && delta < -0.0005
          return (
            <div key={r.code} className="flex items-center gap-3">
              <span className="w-5 shrink-0 text-right text-xs tabular-nums text-ink-faint">
                {i + 1}
              </span>
              <div className="flex w-28 shrink-0 items-center gap-1.5 text-sm">
                <Flag code={r.code} />
                <span className="truncate">{teams?.[r.code]?.name_zh ?? r.code}</span>
              </div>
              <div className="relative h-4 flex-1 overflow-hidden rounded bg-line/60">
                <div
                  className="absolute inset-y-0 left-0 rounded bg-accent"
                  style={{
                    width: pct(Math.max(0.02, r.p / max)),
                    opacity: 0.45 + 0.55 * (r.p / max),
                  }}
                />
              </div>
              <span className="w-11 shrink-0 text-right text-sm tabular-nums">{pct(r.p, 1)}</span>
              <span
                className={`w-14 shrink-0 text-right text-xs tabular-nums ${
                  up ? 'text-accent' : 'text-ink-faint'
                }`}
              >
                {delta == null || (!up && !down)
                  ? '—'
                  : up
                    ? `▲${pct(delta, 1)}`
                    : `▼${pct(-delta, 1)}`}
              </span>
            </div>
          )
        })}
      </section>
    </div>
  )
}
