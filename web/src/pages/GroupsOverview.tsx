import { Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import type { Groups } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import GroupTable from '../components/GroupTable'

export default function GroupsOverview() {
  const { data, loading, error } = useData<Groups>('groups')
  if (loading) return <Loading />
  if (error || !data) return <ErrorMsg msg={error || '无数据'} />

  return (
    <div>
      <h1 className="mb-4 text-xl font-medium">小组赛</h1>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(data).map(([g, teams]) => (
          <Link key={g} to={`/groups/${g}`} className="block">
            <Card className="px-4 py-3 transition-colors hover:bg-surface">
              <div className="mb-1 text-sm font-medium text-ink-secondary">{g} 组</div>
              <GroupTable group={g} teams={teams} />
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
