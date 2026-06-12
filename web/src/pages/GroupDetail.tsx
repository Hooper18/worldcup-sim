import { useParams, Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import type { Groups, Match } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import GroupTable from '../components/GroupTable'
import MatchCard from '../components/MatchCard'

export default function GroupDetail() {
  const { id = '' } = useParams()
  const g = id.toUpperCase()
  const groups = useData<Groups>('groups')
  const matches = useData<Match[]>('matches')

  if (groups.loading || matches.loading) return <Loading />
  if (groups.error || matches.error || !groups.data || !matches.data)
    return <ErrorMsg msg={groups.error || matches.error || '无数据'} />
  const teams = groups.data[g]
  if (!teams) return <ErrorMsg msg={`无 ${g} 组数据`} />

  const groupMatches = matches.data
    .filter((m) => m.stage === 'group' && m.group === g)
    .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link to="/groups" className="text-sm text-ink-faint hover:text-ink-secondary">
          ← 小组赛
        </Link>
        <h1 className="mt-1 text-xl font-medium">{g} 组</h1>
      </div>

      <Card className="px-4 py-3">
        <GroupTable group={g} teams={teams} />
        <p className="mt-3 text-xs text-ink-faint">
          出线率 = 小组前二 + 作为最佳第三晋级的概率（基于 10 万次模拟）
        </p>
      </Card>

      <section>
        <h2 className="mb-3 text-md font-medium text-ink-secondary">6 场比赛</h2>
        <div className="space-y-2">
          {groupMatches.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </div>
      </section>
    </div>
  )
}
