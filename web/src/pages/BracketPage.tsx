import { useData } from '../hooks/useData'
import type { Knockout, Match } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import BracketView from '../components/BracketView'

export default function BracketPage() {
  const matches = useData<Match[]>('matches')
  const ko = useData<Knockout>('knockout')
  if (matches.loading || ko.loading) return <Loading />
  if (matches.error || ko.error || !matches.data || !ko.data)
    return <ErrorMsg msg={matches.error || ko.error || '无数据'} />

  const koMatches = matches.data.filter((m) => m.stage !== 'group')
  return (
    <div>
      <h1 className="mb-1 text-xl font-medium">淘汰赛对阵</h1>
      <p className="mb-4 text-xs text-ink-faint">
        未定槽位显示当前最可能晋级的球队及其概率；点击任意场次查看详情
      </p>
      <BracketView matches={koMatches} knockout={ko.data} />
    </div>
  )
}
