import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import { useTeams } from '../hooks/useTeams'
import type { Evolution, Knockout, Match, Stage } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import TeamLabel from '../components/TeamLabel'
import LineChartSvg from '../components/LineChartSvg'
import { seriesColor, type Series } from '../lib/chart'
import { AFTER_LABEL, formatDay, formatTime, kickoffDateKey } from '../lib/format'
import { koSide } from '../lib/bracket'
import { dedupeEvolution, pickSeries } from '../lib/evolution'

const STAGES: { key: Stage; label: string }[] = [
  { key: 'group', label: '小组赛' },
  { key: 'r32', label: '32 强' },
  { key: 'r16', label: '16 强' },
  { key: 'qf', label: '8 强' },
  { key: 'sf', label: '半决赛' },
  { key: 'third', label: '季军赛' },
  { key: 'final', label: '决赛' },
]

// 小组赛轮次：每组 6 场按时间分成 3 轮
function buildGroupRound(matches: Match[]): Record<number, number> {
  const byGroup: Record<string, Match[]> = {}
  for (const m of matches) {
    if (m.stage === 'group' && m.group) (byGroup[m.group] ??= []).push(m)
  }
  const round: Record<number, number> = {}
  for (const ms of Object.values(byGroup)) {
    ms.sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.id - b.id)
    ms.forEach((m, i) => {
      round[m.id] = Math.floor(i / 2) + 1
    })
  }
  return round
}

function venueCity(v: string): string {
  return v.replace(/\s*Stadium$/i, '').trim()
}

export default function Schedule() {
  const matchesQ = useData<Match[]>('matches')
  const koQ = useData<Knockout>('knockout')
  const evoQ = useData<Evolution>('evolution')
  const teams = useTeams()
  const [stageFilter, setStageFilter] = useState<Stage | 'all'>('all')

  const matches = matchesQ.data
  const ko = koQ.data
  const evo = evoQ.data

  const groupRound = useMemo(() => (matches ? buildGroupRound(matches) : {}), [matches])

  // 顶部：每打一场的夺冠率走势（按 matches_played 去重）
  const chart = useMemo(() => {
    if (!evo || !ko) return null
    const { keepIdx, xLabels } = dedupeEvolution(evo)
    const top = Object.entries(ko.teams)
      .sort((a, b) => b[1].p_champion - a[1].p_champion)
      .slice(0, 6)
      .map(([c]) => c)
    const series: Series[] = top.map((code, i) => ({
      label: teams?.[code]?.name_zh ?? code,
      color: seriesColor(i),
      values: pickSeries(evo.teams[code]?.champion, keepIdx),
    }))
    return { series, xLabels }
  }, [evo, ko, teams])

  if (matchesQ.loading || koQ.loading || evoQ.loading) return <Loading />
  if (matchesQ.error || !matches || koQ.error || !ko || evoQ.error || !evo)
    return <ErrorMsg msg={matchesQ.error || koQ.error || evoQ.error || '无数据'} />

  const played = matches.filter((m) => m.status === 'finished').length

  const visibleStages = STAGES.filter((s) => stageFilter === 'all' || s.key === stageFilter)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-medium">赛程</h1>
        <p className="mt-1 text-xs text-ink-faint">
          全 104 场（北京时间）· 已赛 {played}/104 · 比分为真实赛果，其余为待赛
        </p>
      </div>

      {/* 每打一场 · 夺冠概率走势 */}
      {chart && (
        <Card className="px-4 py-4">
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-sm font-medium">每打一场 · 夺冠概率走势</h2>
            <Link to="/trends" className="text-xs text-accent hover:underline">
              更多指标与选队 →
            </Link>
          </div>
          <LineChartSvg series={chart.series} xLabels={chart.xLabels} />
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
            {chart.series.map((s, i) => (
              <span key={i} className="flex items-center gap-1.5 text-xs text-ink-secondary">
                <span
                  className="inline-block h-2 w-3 rounded"
                  style={{ backgroundColor: s.color }}
                />
                {s.label}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-faint">
            横轴为已赛场数；每回填一批真实赛果即条件化重模拟 10 万次，追踪夺冠概率的变化
          </p>
        </Card>
      )}

      {/* 阶段筛选 */}
      <div className="flex flex-wrap gap-1">
        {(
          [{ key: 'all', label: '全部' }, ...STAGES] as { key: Stage | 'all'; label: string }[]
        ).map((s) => (
          <button
            key={s.key}
            onClick={() => setStageFilter(s.key)}
            className={`rounded-lg px-3 py-1 text-sm transition-colors ${
              stageFilter === s.key
                ? 'bg-accent-soft text-accent'
                : 'text-ink-secondary hover:bg-surface'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* 时间轴：阶段 → 日期 → 比赛 */}
      <div className="space-y-8">
        {visibleStages.map(({ key, label }) => {
          const ms = matches
            .filter((m) => m.stage === key)
            .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.id - b.id)
          if (!ms.length) return null

          // 按本地日期分组
          const days: { key: string; label: string; items: Match[] }[] = []
          for (const m of ms) {
            const dk = kickoffDateKey(m.kickoff_utc)
            let bucket = days.find((d) => d.key === dk)
            if (!bucket) {
              bucket = { key: dk, label: formatDay(m.kickoff_utc), items: [] }
              days.push(bucket)
            }
            bucket.items.push(m)
          }
          const stagePlayed = ms.filter((m) => m.status === 'finished').length

          return (
            <section key={key}>
              <div className="mb-3 flex items-baseline gap-2 border-b border-line pb-1.5">
                <h2 className="text-md font-medium">{label}</h2>
                <span className="text-xs text-ink-faint">
                  {ms.length} 场{stagePlayed ? ` · 已赛 ${stagePlayed}` : ''}
                </span>
              </div>
              <div className="space-y-4">
                {days.map((d) => (
                  <div key={d.key}>
                    <div className="mb-1.5 text-xs font-medium text-ink-secondary">{d.label}</div>
                    <div className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-card/40">
                      {d.items.map((m) => (
                        <ScheduleRow
                          key={m.id}
                          match={m}
                          bracket={ko.bracket}
                          resolved={(c) => !!(c && teams?.[c])}
                          round={m.stage === 'group' ? groupRound[m.id] : undefined}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}

function Side({
  match,
  side,
  bracket,
  resolved,
  align,
}: {
  match: Match
  side: 'home' | 'away'
  bracket: Knockout['bracket']
  resolved: (c: string | null) => boolean
  align: 'left' | 'right'
}) {
  const code = side === 'home' ? match.home : match.away
  if (resolved(code)) {
    return <TeamLabel code={code} className={align === 'right' ? 'flex-row-reverse' : ''} />
  }
  // 未定队（淘汰赛对阵位）：显示占位描述
  const text = match.stage === 'group' ? '待定' : koSide(bracket, match.id, side)
  return <span className="text-sm text-ink-faint">{text}</span>
}

function ScheduleRow({
  match,
  bracket,
  resolved,
  round,
}: {
  match: Match
  bracket: Knockout['bracket']
  resolved: (c: string | null) => boolean
  round?: number
}) {
  const { result, status } = match
  return (
    <Link
      to={`/match/${match.id}`}
      className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-surface"
    >
      <div className="w-11 shrink-0 text-xs tabular-nums text-ink-faint">
        {formatTime(match.kickoff_utc)}
      </div>
      <div className="grid flex-1 grid-cols-[1fr_auto_1fr] items-center gap-2">
        <div className="flex justify-end">
          <Side match={match} side="home" bracket={bracket} resolved={resolved} align="right" />
        </div>
        <div className="min-w-[3.5rem] text-center text-sm tabular-nums">
          {result ? (
            <span className="font-medium">
              {result.h} : {result.a}
              {result.after !== 'FT' && (
                <span className="ml-0.5 text-xs text-ink-faint">{AFTER_LABEL[result.after]}</span>
              )}
            </span>
          ) : (
            <span className="text-ink-faint">vs</span>
          )}
        </div>
        <div className="flex justify-start">
          <Side match={match} side="away" bracket={bracket} resolved={resolved} align="left" />
        </div>
      </div>
      <div className="hidden w-32 shrink-0 text-right text-xs text-ink-faint sm:block">
        {round ? <span className="mr-1.5 text-ink-faint/80">第{round}轮</span> : null}
        {status === 'finished' ? '' : venueCity(match.venue)}
      </div>
    </Link>
  )
}
