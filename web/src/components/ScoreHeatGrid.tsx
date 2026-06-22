import { pct } from '../lib/format'
import Flag from './Flag'

interface Props {
  matrix: number[][] // 6x6，[主队进球][客队进球]
  homeCode?: string | null
  awayCode?: string | null
}

// 比分概率热力格（纯 CSS grid + 透明度映射，不用图表库）。
export default function ScoreHeatGrid({ matrix, homeCode, awayCode }: Props) {
  const max = Math.max(...matrix.flat(), 0.001)
  return (
    <div className="inline-block">
      <div className="mb-1 flex items-center justify-center gap-1 text-xs text-ink-faint">
        客队进球 <Flag code={awayCode} /> →
      </div>
      <div className="flex">
        <div className="mr-1 flex flex-col items-center justify-center gap-1 text-xs text-ink-faint">
          <span className="[writing-mode:vertical-rl]">↓ 主队进球</span>
          <Flag code={homeCode} />
        </div>
        <div>
          <div className="grid grid-cols-6 gap-0.5">
            {matrix.map((row, h) =>
              row.map((p, a) => (
                <div
                  key={`${h}-${a}`}
                  title={`${h} : ${a} — ${pct(p, 1)}`}
                  className="flex aspect-square w-9 items-center justify-center rounded text-xs tabular-nums"
                  style={{
                    backgroundColor: `rgb(var(--c-accent) / ${0.06 + 0.94 * (p / max)})`,
                    color: p / max > 0.5 ? '#fff' : 'rgb(var(--c-ink-secondary))',
                  }}
                >
                  {h}:{a}
                </div>
              )),
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
