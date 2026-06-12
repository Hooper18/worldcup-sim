import { useData } from '../hooks/useData'
import type { Knockout, Match, Meta } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import ChampionBar from '../components/ChampionBar'
import MatchCard from '../components/MatchCard'
import { formatKickoff, kickoffDateKey, todayKey } from '../lib/format'

export default function Dashboard() {
  const meta = useData<Meta>('meta')
  const ko = useData<Knockout>('knockout')
  const matches = useData<Match[]>('matches')

  if (meta.loading || ko.loading || matches.loading) return <Loading />
  if (meta.error || ko.error || matches.error)
    return <ErrorMsg msg={meta.error || ko.error || matches.error || '加载失败'} />
  if (!meta.data || !ko.data || !matches.data) return <ErrorMsg msg="无数据" />

  const champTop = Object.entries(ko.data.teams)
    .map(([code, t]) => ({ code, p: t.p_champion }))
    .sort((a, b) => b.p - a.p)
    .slice(0, 10)

  // 今日 / 下一个比赛日的赛程
  const today = todayKey()
  const upcoming = matches.data
    .filter((m) => m.status === 'scheduled')
    .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))
  const todayMatches = upcoming.filter((m) => kickoffDateKey(m.kickoff_utc) === today)
  const nextDay = todayMatches.length
    ? todayMatches
    : upcoming.slice(0, 1).length
      ? upcoming.filter((m) => kickoffDateKey(m.kickoff_utc) === kickoffDateKey(upcoming[0].kickoff_utc))
      : []
  const dayLabel = todayMatches.length ? '今日赛程' : nextDay.length ? '下一比赛日' : '赛程'

  // 最近完赛
  const finished = matches.data
    .filter((m) => m.status === 'finished')
    .sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc))
    .slice(0, 3)

  return (
    <div className="space-y-6">
      <StatusBar meta={meta.data} />

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <section>
          <h2 className="mb-3 text-lg font-medium">夺冠概率</h2>
          <Card className="px-4 py-4">
            <ChampionBar data={champTop} />
          </Card>
        </section>

        <div className="space-y-6">
          {nextDay.length > 0 && (
            <section>
              <h2 className="mb-1 text-lg font-medium">{dayLabel}</h2>
              <p className="mb-3 text-xs text-ink-faint">
                {formatKickoff(nextDay[0].kickoff_utc).split(' ').slice(0, 2).join(' ')}
              </p>
              <div className="space-y-2">
                {nextDay.map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </section>
          )}

          {finished.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-medium">最近完赛</h2>
              <div className="space-y-2">
                {finished.map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusBar({ meta }: { meta: Meta }) {
  const items = [
    { label: '已完赛', value: `${meta.matches_played} / 104` },
    { label: '模拟次数', value: `${(meta.n_sims / 10000).toFixed(0)} 万` },
    { label: '历史样本', value: `${(meta.data.martj42_rows / 1000).toFixed(0)}k 场` },
    { label: '更新时间', value: formatKickoff(meta.generated_at).split(' ').slice(0, 1) + ' 更新' },
  ]
  return (
    <Card className="flex flex-wrap gap-x-6 gap-y-2 px-4 py-3 text-sm">
      {items.map((it) => (
        <div key={it.label}>
          <span className="text-ink-faint">{it.label}</span>
          <span className="ml-2 text-ink">{it.value}</span>
        </div>
      ))}
    </Card>
  )
}
