// 自绘多序列折线图（SVG，不依赖图表库，保证渲染）。
// x 为数据点序号（标签由 xLabels 提供，本项目即已赛场数），y 为概率 [0, yMax]。
// 鼠标移上去显示参考线 + 各序列具体数值。

import { useRef, useState } from 'react'
import type { Series } from '../lib/chart'

interface Props {
  series: Series[]
  xLabels: string[]
  yMax?: number
  height?: number
  valueFmt?: (v: number) => string // 提示框数值格式（默认百分比）
  yFmt?: (v: number) => string // y 轴刻度格式（默认百分比；RPS 等非百分比指标可覆盖）
}

export default function LineChartSvg({
  series,
  xLabels,
  yMax,
  height = 240,
  valueFmt,
  yFmt,
}: Props) {
  const W = 640
  const H = height
  const padL = 36
  const padR = 12
  const padT = 12
  const padB = 28
  const n = xLabels.length
  const maxY = yMax ?? Math.max(0.05, ...series.flatMap((s) => s.values))
  const x = (i: number) => padL + (n <= 1 ? 0 : (i * (W - padL - padR)) / (n - 1))
  const y = (v: number) => padT + (1 - v / maxY) * (H - padT - padB)
  const fmt = valueFmt ?? ((v: number) => `${(v * 100).toFixed(1)}%`)
  const yfmt = yFmt ?? ((v: number) => `${(v * 100).toFixed(0)}%`)

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxY)

  const svgRef = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg || n === 0) return
    const rect = svg.getBoundingClientRect()
    if (rect.width === 0) return
    const vbX = ((e.clientX - rect.left) / rect.width) * W
    let i = n <= 1 ? 0 : Math.round(((vbX - padL) / (W - padL - padR)) * (n - 1))
    i = Math.max(0, Math.min(n - 1, i))
    setHover(i)
  }

  const ordered =
    hover === null
      ? []
      : [...series].sort((a, b) => (b.values[hover] ?? 0) - (a.values[hover] ?? 0))
  const leftPct = hover === null ? 0 : (x(hover) / W) * 100
  const flip = leftPct > 60

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        role="img"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {/* y 网格 + 刻度 */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={padL}
              y1={y(t)}
              x2={W - padR}
              y2={y(t)}
              stroke="rgb(var(--c-line))"
              strokeWidth={1}
            />
            <text
              x={padL - 6}
              y={y(t) + 3}
              textAnchor="end"
              fontSize={10}
              fill="rgb(var(--c-ink-faint))"
            >
              {yfmt(t)}
            </text>
          </g>
        ))}
        {/* x 标签（最多 6 个，避免拥挤） */}
        {xLabels.map((lab, i) => {
          const step = Math.ceil(n / 6)
          if (i % step !== 0 && i !== n - 1) return null
          return (
            <text
              key={i}
              x={x(i)}
              y={H - 10}
              textAnchor="middle"
              fontSize={10}
              fill="rgb(var(--c-ink-faint))"
            >
              {lab}
            </text>
          )
        })}
        {/* hover 参考线 */}
        {hover !== null && (
          <line
            x1={x(hover)}
            y1={padT}
            x2={x(hover)}
            y2={H - padB}
            stroke="rgb(var(--c-ink-faint))"
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        )}
        {/* 折线 + 端点 */}
        {series.map((s, si) => {
          if (!s.values.length) return null
          const d = s.values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(v)}`).join(' ')
          return (
            <g key={si}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2} />
              {n === 1 && <circle cx={x(0)} cy={y(s.values[0])} r={3} fill={s.color} />}
              <circle cx={x(n - 1)} cy={y(s.values[n - 1])} r={3} fill={s.color} />
            </g>
          )
        })}
        {/* hover 数据点 */}
        {hover !== null &&
          series.map((s, si) =>
            s.values[hover] == null ? null : (
              <circle
                key={si}
                cx={x(hover)}
                cy={y(s.values[hover])}
                r={3.5}
                fill={s.color}
                stroke="rgb(var(--c-paper))"
                strokeWidth={1}
              />
            ),
          )}
      </svg>

      {/* 数值提示框 */}
      {hover !== null && (
        <div
          className={`pointer-events-none absolute top-1 z-10 ${flip ? '-translate-x-full -ml-2' : 'ml-2'}`}
          style={{ left: `${leftPct}%` }}
        >
          <div className="min-w-[7rem] rounded-lg border border-line bg-card px-2.5 py-1.5">
            <div className="mb-1 text-[11px] font-medium text-ink-secondary">{xLabels[hover]}</div>
            <div className="space-y-0.5">
              {ordered.map((s) => (
                <div
                  key={s.label}
                  className="flex items-center justify-between gap-3 text-[11px] leading-tight"
                >
                  <span className="flex items-center gap-1.5 text-ink-secondary">
                    <span
                      className="inline-block h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: s.color }}
                    />
                    {s.label}
                  </span>
                  <span className="tabular-nums text-ink">{fmt(s.values[hover] ?? 0)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
