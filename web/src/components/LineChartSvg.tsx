// 自绘多序列折线图（SVG，不依赖图表库，保证渲染）。
// x 为快照序号，y 为概率 [0, yMax]。

export interface Series {
  label: string
  color: string
  values: number[]
}

interface Props {
  series: Series[]
  xLabels: string[]
  yMax?: number
  height?: number
}

const PALETTE = ['#2F6B4F', '#B5651D', '#3A5A8C', '#7A4E8C', '#8C5A3A', '#4A7A6A']

export function seriesColor(i: number): string {
  return PALETTE[i % PALETTE.length]
}

export default function LineChartSvg({ series, xLabels, yMax, height = 240 }: Props) {
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

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxY)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
      {/* y 网格 + 刻度 */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)} stroke="#E7E4DE" strokeWidth={1} />
          <text x={padL - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="#9C9A96">
            {(t * 100).toFixed(0)}%
          </text>
        </g>
      ))}
      {/* x 标签（最多 6 个，避免拥挤） */}
      {xLabels.map((lab, i) => {
        const step = Math.ceil(n / 6)
        if (i % step !== 0 && i !== n - 1) return null
        return (
          <text key={i} x={x(i)} y={H - 10} textAnchor="middle" fontSize={10} fill="#9C9A96">
            {lab}
          </text>
        )
      })}
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
    </svg>
  )
}
