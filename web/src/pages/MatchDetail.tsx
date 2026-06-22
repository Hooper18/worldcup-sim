import { useParams, Link } from 'react-router-dom'
import { useData } from '../hooks/useData'
import { useTeams } from '../hooks/useTeams'
import type { Match } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import ProbBar from '../components/ProbBar'
import ScoreHeatGrid from '../components/ScoreHeatGrid'
import TeamLabel from '../components/TeamLabel'
import { AFTER_LABEL, formatKickoff, STAGE_LABEL } from '../lib/format'

export default function MatchDetail() {
  const { id = '' } = useParams()
  const matches = useData<Match[]>('matches')
  const teams = useTeams()
  if (matches.loading) return <Loading />
  if (matches.error || !matches.data) return <ErrorMsg msg={matches.error || '无数据'} />
  const m = matches.data.find((x) => x.id === Number(id))
  if (!m) return <ErrorMsg msg="未找到该场比赛" />

  const isKnockout = m.stage !== 'group'
  const homeName = m.home && !isKnockout ? m.home : (m.slot_dist?.home[0]?.team ?? m.home)
  const awayName = m.away && !isKnockout ? m.away : (m.slot_dist?.away[0]?.team ?? m.away)

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link to="/bracket" className="text-sm text-ink-faint hover:text-ink-secondary">
          ← 返回
        </Link>
        <div className="mt-1 flex items-center justify-between text-xs text-ink-faint">
          <span>
            {STAGE_LABEL[m.stage]}
            {m.group ? ` · ${m.group} 组` : ''}
          </span>
          <span>
            {formatKickoff(m.kickoff_utc)} · {m.venue}
          </span>
        </div>
      </div>

      {/* 比分 / 对阵 */}
      <Card className="px-6 py-5">
        <div className="flex items-center justify-around">
          <TeamLabel code={homeName} size="md" />
          <div className="text-center">
            {m.result ? (
              <>
                <div className="text-2xl font-medium tabular-nums">
                  {m.result.h} : {m.result.a}
                </div>
                {m.result.after !== 'FT' && (
                  <div className="text-xs text-ink-faint">
                    {AFTER_LABEL[m.result.after]}
                    {m.result.after === 'PEN' &&
                      `（${m.result.pen_winner === 'home' ? '主队' : '客队'}胜出）`}
                  </div>
                )}
              </>
            ) : (
              <span className="text-ink-faint">vs</span>
            )}
          </div>
          <TeamLabel code={awayName} size="md" className="flex-row-reverse" />
        </div>
      </Card>

      {/* 淘汰赛槽位归属 */}
      {isKnockout && m.slot_dist && (
        <section>
          <h2 className="mb-2 text-md font-medium text-ink-secondary">谁会踢这场</h2>
          <div className="grid grid-cols-2 gap-4">
            {(['home', 'away'] as const).map((side) => (
              <Card key={side} className="px-4 py-3">
                <div className="mb-2 text-xs text-ink-faint">
                  {side === 'home' ? '一方' : '另一方'}
                </div>
                {m.slot_dist![side].map((s) => (
                  <div key={s.team} className="flex justify-between py-0.5 text-sm">
                    <TeamLabel code={s.team} size="sm" />
                    <span className="tabular-nums text-ink-secondary">
                      {(s.p * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* 预测（小组赛对阵确定才有 forecast） */}
      {m.forecast && (
        <>
          <section>
            <h2 className="mb-3 text-md font-medium text-ink-secondary">
              {m.status === 'finished' ? '赛前预测' : '比分预测'}
            </h2>
            <Card className="space-y-4 px-4 py-4">
              <ProbBar
                pHome={m.forecast.p_home}
                pDraw={m.forecast.p_draw}
                pAway={m.forecast.p_away}
                labels={[
                  teams?.[homeName ?? '']?.name_zh ?? '主',
                  teams?.[awayName ?? '']?.name_zh ?? '客',
                ]}
              />
              <div className="text-xs text-ink-faint">
                预期进球 λ：{m.forecast.lambda_home} — {m.forecast.lambda_away}
              </div>
            </Card>
          </section>

          <section>
            <h2 className="mb-3 text-md font-medium text-ink-secondary">最可能比分</h2>
            <div className="flex flex-wrap gap-2">
              {m.forecast.top_scores.slice(0, 6).map((s, i) => (
                <span
                  key={i}
                  className="rounded-lg border border-line bg-white/40 px-3 py-1.5 text-sm tabular-nums"
                >
                  {s.h}:{s.a}
                  <span className="ml-1.5 text-xs text-ink-faint">{(s.p * 100).toFixed(1)}%</span>
                </span>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-md font-medium text-ink-secondary">比分概率热力</h2>
            <Card className="overflow-x-auto px-4 py-4">
              <ScoreHeatGrid
                matrix={m.forecast.score_matrix}
                homeCode={homeName}
                awayCode={awayName}
              />
            </Card>
          </section>

          {m.model_breakdown && (
            <section>
              <h2 className="mb-3 text-md font-medium text-ink-secondary">分模型预测</h2>
              <Card className="space-y-3 px-4 py-4">
                {Object.entries(m.model_breakdown).map(([id, b]) => (
                  <div key={id}>
                    <div className="mb-1 text-xs text-ink-faint">
                      {id === 'dc_elo' ? 'DC-on-Elo' : '纯攻防 Dixon-Coles'}
                    </div>
                    <ProbBar pHome={b.p_home} pDraw={b.p_draw} pAway={b.p_away} />
                  </div>
                ))}
              </Card>
            </section>
          )}
        </>
      )}
    </div>
  )
}
