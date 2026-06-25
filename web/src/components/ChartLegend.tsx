import type { Series } from '../lib/chart'

// 折线图图例：色块 + 标签（多页复用，统一样式）。
export default function ChartLegend({
  series,
  className = '',
}: {
  series: Series[]
  className?: string
}) {
  return (
    <div className={`flex flex-wrap gap-x-3 gap-y-1.5 text-xs text-ink-secondary ${className}`}>
      {series.map((s, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded" style={{ backgroundColor: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}
