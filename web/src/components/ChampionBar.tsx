import { useTeams } from '../hooks/useTeams'
import { pct } from '../lib/format'
import Flag from './Flag'

interface Props {
  data: { code: string; p: number }[]
}

// 夺冠概率横向条形（纯 CSS，不依赖图表库）。单色系，越高越深。
export default function ChampionBar({ data }: Props) {
  const teams = useTeams()
  const max = Math.max(...data.map((d) => d.p), 0.01)
  return (
    <div className="space-y-2">
      {data.map((d) => {
        const t = teams?.[d.code]
        return (
          <div key={d.code} className="flex items-center gap-3">
            <div className="flex w-24 shrink-0 items-center gap-1.5 text-sm">
              <Flag code={d.code} />
              <span className="truncate">{t?.name_zh ?? d.code}</span>
            </div>
            <div className="h-4 flex-1 overflow-hidden rounded bg-line/60">
              <div
                className="h-full rounded bg-accent"
                style={{ width: pct(Math.max(0.02, d.p / max)), opacity: 0.45 + 0.55 * (d.p / max) }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-sm tabular-nums text-ink-secondary">
              {pct(d.p, 1)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
