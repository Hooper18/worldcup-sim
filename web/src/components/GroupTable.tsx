import type { GroupTeam } from '../types/data'
import { pct } from '../lib/format'
import TeamLabel from './TeamLabel'

interface Props {
  group: string
  teams: Record<string, GroupTeam>
}

// 积分榜 + 出线概率合并表。按出线概率降序。
export default function GroupTable({ teams }: Props) {
  const rows = Object.entries(teams).sort((a, b) => b[1].p_advance - a[1].p_advance)
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-ink-faint">
          <th className="py-1.5 text-left font-normal">球队</th>
          <th className="py-1.5 text-right font-normal">积分</th>
          <th className="py-1.5 text-right font-normal">净胜</th>
          <th className="py-1.5 text-right font-normal">出线率</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([code, t]) => (
          <tr key={code} className="border-t border-line">
            <td className="py-2">
              <TeamLabel code={code} size="sm" />
            </td>
            <td className="py-2 text-right tabular-nums text-ink-secondary">
              {t.current?.played ? (
                t.current.pts
              ) : (
                <span className="text-ink-faint">{t.exp_pts}</span>
              )}
            </td>
            <td className="py-2 text-right tabular-nums text-ink-secondary">
              {t.current?.played ? (
                t.current.gd > 0 ? (
                  `+${t.current.gd}`
                ) : (
                  t.current.gd
                )
              ) : (
                <span className="text-ink-faint">{t.exp_gd > 0 ? `+${t.exp_gd}` : t.exp_gd}</span>
              )}
            </td>
            <td className="py-2 text-right">
              <div className="flex items-center justify-end gap-2">
                <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full bg-accent"
                    style={{ width: pct(Math.min(1, t.p_advance)) }}
                  />
                </div>
                <span className="w-10 tabular-nums text-ink">{pct(t.p_advance)}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
