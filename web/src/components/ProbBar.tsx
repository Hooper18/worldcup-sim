import { pct } from '../lib/format'

interface Props {
  pHome: number
  pDraw: number
  pAway: number
  labels?: [string, string] // [主, 客]
}

// 三段式胜平负概率条：主队（深绿）/ 平（浅灰）/ 客队（中灰）。同色系，不用多彩。
export default function ProbBar({ pHome, pDraw, pAway, labels }: Props) {
  const clamp = (x: number) => Math.max(0, Math.min(1, x || 0))
  const h = clamp(pHome)
  const d = clamp(pDraw)
  const a = clamp(pAway)
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-line">
        <div style={{ width: pct(h) }} className="bg-accent" />
        <div style={{ width: pct(d) }} className="bg-ink-faint/40" />
        <div style={{ width: pct(a) }} className="bg-ink-secondary/70" />
      </div>
      <div className="mt-1 flex justify-between text-xs text-ink-secondary">
        <span>
          {labels?.[0] ?? '主胜'} {pct(h)}
        </span>
        <span>平 {pct(d)}</span>
        <span>
          {labels?.[1] ?? '客胜'} {pct(a)}
        </span>
      </div>
    </div>
  )
}
