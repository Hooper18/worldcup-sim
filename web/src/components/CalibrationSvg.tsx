// 校准曲线（SVG 散点 + 对角线）。点越接近对角线说明预测概率越可信。

interface Props {
  points: number[][] // [[平均预测, 经验频率, 样本数], ...]
}

export default function CalibrationSvg({ points }: Props) {
  const S = 220
  const pad = 28
  const x = (v: number) => pad + v * (S - 2 * pad)
  const y = (v: number) => S - pad - v * (S - 2 * pad)
  const maxN = Math.max(...points.map((p) => p[2]), 1)

  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[260px]" role="img">
      {/* 对角线（完美校准） */}
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(1)}
        y2={y(1)}
        stroke="rgb(var(--c-line))"
        strokeWidth={1}
        strokeDasharray="3 3"
      />
      {/* 轴 */}
      <line x1={pad} y1={S - pad} x2={S - pad} y2={S - pad} stroke="rgb(var(--c-line))" />
      <line x1={pad} y1={pad} x2={pad} y2={S - pad} stroke="rgb(var(--c-line))" />
      <text x={S / 2} y={S - 6} textAnchor="middle" fontSize={10} fill="rgb(var(--c-ink-faint))">
        预测概率
      </text>
      <text
        x={10}
        y={S / 2}
        textAnchor="middle"
        fontSize={10}
        fill="rgb(var(--c-ink-faint))"
        transform={`rotate(-90 10 ${S / 2})`}
      >
        实际频率
      </text>
      {/* 点（大小 ~ 样本数） */}
      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(p[0])}
          cy={y(p[1])}
          r={3 + 4 * (p[2] / maxN)}
          fill="rgb(var(--c-accent))"
          fillOpacity={0.55}
        />
      ))}
    </svg>
  )
}
