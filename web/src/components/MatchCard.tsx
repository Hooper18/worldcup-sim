import { Link } from 'react-router-dom'
import type { Match } from '../types/data'
import { AFTER_LABEL, formatKickoff, STAGE_LABEL } from '../lib/format'
import TeamLabel from './TeamLabel'
import ProbBar from './ProbBar'

// 列表用比赛卡：已完赛显示比分，未赛显示胜平负概率条。
export default function MatchCard({ match }: { match: Match }) {
  const { home, away, result, forecast, status } = match
  return (
    <Link
      to={`/match/${match.id}`}
      className="block rounded-xl border border-line bg-card/40 px-4 py-3 transition-colors hover:bg-surface"
    >
      <div className="mb-2 flex items-center justify-between text-xs text-ink-faint">
        <span>
          {STAGE_LABEL[match.stage]}
          {match.group ? ` · ${match.group} 组` : ''}
        </span>
        <span>{formatKickoff(match.kickoff_utc)}</span>
      </div>
      <div className="mb-2 flex items-center justify-between">
        <TeamLabel code={home} />
        <span className="font-medium tabular-nums">
          {result ? (
            <>
              {result.h} : {result.a}
              {result.after !== 'FT' && (
                <span className="ml-1 text-xs text-ink-faint">{AFTER_LABEL[result.after]}</span>
              )}
            </>
          ) : (
            <span className="text-ink-faint">vs</span>
          )}
        </span>
        <TeamLabel code={away} className="flex-row-reverse" />
      </div>
      {status === 'scheduled' && forecast && (
        <ProbBar pHome={forecast.p_home} pDraw={forecast.p_draw} pAway={forecast.p_away} />
      )}
    </Link>
  )
}
