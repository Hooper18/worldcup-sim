import { useTeams } from '../hooks/useTeams'
import { pct } from '../lib/format'
import Flag from './Flag'

interface Props {
  data: { code: string; p: number }[]
  ci?: Record<string, number[]> // code -> [lo, med, hi]（bootstrap 95% 区间）
}

// 夺冠概率横向条形（纯 CSS，不依赖图表库）。单色系，越高越深。
// 有 bootstrap 区间时，条上叠一段更淡的 [lo,hi] 误差带，并在右侧标注 95% 区间。
export default function ChampionBar({ data, ci }: Props) {
  const teams = useTeams()
  const max = Math.max(...data.map((d) => d.p), 0.01)
  return (
    <div className="space-y-2">
      {data.map((d) => {
        const t = teams?.[d.code]
        const iv = ci?.[d.code]
        return (
          <div key={d.code} className="flex items-center gap-3">
            <div className="flex w-24 shrink-0 items-center gap-1.5 text-sm">
              <Flag code={d.code} />
              <span className="truncate">{t?.name_zh ?? d.code}</span>
            </div>
            <div className="relative h-4 flex-1 overflow-hidden rounded bg-line/60">
              {iv && (
                <div
                  className="absolute inset-y-0 bg-accent/20"
                  style={{ left: pct(iv[0] / max), width: pct(Math.max(0, (iv[2] - iv[0]) / max)) }}
                />
              )}
              <div
                className="absolute inset-y-0 left-0 rounded bg-accent"
                style={{
                  width: pct(Math.max(0.02, d.p / max)),
                  opacity: 0.45 + 0.55 * (d.p / max),
                }}
              />
            </div>
            <span className="shrink-0 text-right text-sm tabular-nums text-ink-secondary">
              <span className="inline-block w-11">{pct(d.p, 1)}</span>
              {iv && (
                <span className="ml-1 text-xs text-ink-faint">
                  {pct(iv[0])}–{pct(iv[2])}
                </span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}
