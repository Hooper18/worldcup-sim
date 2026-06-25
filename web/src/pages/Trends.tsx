import { useMemo, useState } from 'react'
import { useData } from '../hooks/useData'
import { useTeams } from '../hooks/useTeams'
import type { Evolution, Knockout } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import Flag from '../components/Flag'
import LineChartSvg from '../components/LineChartSvg'
import ChartLegend from '../components/ChartLegend'
import { seriesColor, type Series } from '../lib/chart'
import { dedupeEvolution, pickSeries } from '../lib/evolution'
import { topChampions } from '../lib/rank'

type Metric = 'champion' | 'sf' | 'advance'
const METRIC_LABEL: Record<Metric, string> = { champion: '夺冠', sf: '进四强', advance: '出线' }

export default function Trends() {
  const evo = useData<Evolution>('evolution')
  const ko = useData<Knockout>('knockout')
  const teams = useTeams()
  const [metric, setMetric] = useState<Metric>('champion')

  // 默认选中：当前夺冠概率 Top6
  const defaultSel = useMemo(
    () => (ko.data ? topChampions(ko.data.teams, 6).map((x) => x.code) : []),
    [ko.data],
  )
  const [selected, setSelected] = useState<string[] | null>(null)
  const sel = selected ?? defaultSel

  if (evo.loading || ko.loading) return <Loading />
  if (evo.error || ko.error || !evo.data || !ko.data)
    return <ErrorMsg msg={evo.error || ko.error || '无数据'} />

  const snaps = evo.data.snapshots
  const { keepIdx, xLabels } = dedupeEvolution(evo.data)
  const series: Series[] = sel.map((code, i) => ({
    label: teams?.[code]?.name_zh ?? code,
    color: seriesColor(i),
    values: pickSeries(evo.data!.teams[code]?.[metric], keepIdx),
  }))

  const candidates = topChampions(ko.data.teams, 16).map((x) => x.code)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-medium">概率演变</h1>
        <p className="mt-1 text-xs text-ink-faint">
          每次回填真实赛果后重新模拟，追踪各队概率随赛事推进的变化
        </p>
      </div>

      <div className="flex gap-1">
        {(Object.keys(METRIC_LABEL) as Metric[]).map((mt) => (
          <button
            key={mt}
            onClick={() => setMetric(mt)}
            className={`rounded-lg px-3 py-1 text-sm transition-colors ${
              metric === mt ? 'bg-accent-soft text-accent' : 'text-ink-secondary hover:bg-surface'
            }`}
          >
            {METRIC_LABEL[mt]}
          </button>
        ))}
      </div>

      <Card className="px-4 py-4">
        {snaps.length < 2 ? (
          <p className="py-8 text-center text-sm text-ink-faint">
            目前仅 {snaps.length} 个快照，赛事推进后这里会显示概率演变曲线
          </p>
        ) : (
          <LineChartSvg series={series} xLabels={xLabels} />
        )}
        <ChartLegend series={series} className="mt-3" />
      </Card>

      <section>
        <h2 className="mb-2 text-sm text-ink-faint">选择球队（夺冠热门 Top16）</h2>
        <div className="flex flex-wrap gap-2">
          {candidates.map((c) => {
            const on = sel.includes(c)
            return (
              <button
                key={c}
                onClick={() =>
                  setSelected(on ? sel.filter((x) => x !== c) : [...sel, c].slice(0, 8))
                }
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-sm transition-colors ${
                  on
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-line text-ink-secondary hover:bg-surface'
                }`}
              >
                <Flag code={c} /> {teams?.[c]?.name_zh ?? c}
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
