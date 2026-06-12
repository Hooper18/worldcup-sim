import { useData } from '../hooks/useData'
import type { Backtest, Meta } from '../types/data'
import { Loading, ErrorMsg } from '../components/Loading'
import Card from '../components/Card'
import CalibrationSvg from '../components/CalibrationSvg'

export default function ModelPage() {
  const { data, loading, error } = useData<Meta>('meta')
  if (loading) return <Loading />
  if (error || !data) return <ErrorMsg msg={error || '无数据'} />

  const comps = data.models.components
  const bt = data.models.backtest as Backtest
  const hasBacktest = bt && 'years' in bt

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-xl font-medium">预测模型</h1>
        <p className="mt-1 text-xs text-ink-faint">基于 {(data.data.martj42_rows / 1000).toFixed(0)}k 场国际比赛历史，融合两个统计模型</p>
      </div>

      <section className="space-y-3">
        <Prose title="怎么预测每场比分">
          每支球队的实力用历史战绩刻画，转换成两队各自的「预期进球数 λ」，再用泊松分布
          （Poisson）算出每个具体比分（0:0、2:1……）的概率。低比分（平局）按 Dixon-Coles
          方法做了修正，让平局概率更贴近真实。
        </Prose>
        <Prose title="两个模型，加权融合">
          <b>DC-on-Elo</b>：把每队压成一个 Elo 实力分（参考 eloratings.net 算法，世界杯权重最高、
          友谊赛最低），用实力差预测进球。
          <br />
          <b>纯攻防 Dixon-Coles</b>：分别刻画每队的「进攻能力」和「防守漏洞」，比单一 Elo 更细。
          <br />
          两者对同一场给出各自概率，按回测最优权重{' '}
          {comps.map((c) => `${c.name_zh.split('（')[0]} ${(c.weight * 100).toFixed(0)}%`).join(' · ')}{' '}
          融合。融合通常比任一单模型在样本外更稳。
        </Prose>
        <Prose title="模拟整届赛事">
          把 104 场逐场按概率随机抽一个比分，按真实赛制（含 2026 头对头排名规则、8 个最佳第三的
          官方落位表）推进到冠军，重复 {(data.n_sims / 10000).toFixed(0)} 万次，统计每队夺冠/出线的频率。
          淘汰赛平局走加时（进球率按比例缩减），仍平则点球——点球胜率由各队历史点球大战战绩
          （Bradley-Terry 模型，强收缩到接近 50:50）微调，而非一律掷硬币。真实赛果出来后固定该场、只重抽未赛场次。
        </Prose>
      </section>

      <section>
        <h2 className="mb-1 text-lg font-medium">回测验证</h2>
        <p className="mb-3 text-xs text-ink-faint">
          纳入 2014 年以来世界杯/欧洲杯/美洲杯/非洲杯/亚洲杯各届决赛圈，用<b>留一届交叉验证</b>：
          每届的参数只在其余赛事上选、在该届做样本外预测，杜绝"同集选参又评估"的乐观偏置。RPS / log-loss 越低越准。
        </p>
        {hasBacktest && bt.loto ? (
          <Card className="space-y-4 px-4 py-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="样本外 RPS" value={bt.loto.oos_rps.toFixed(3)} hint={`基准 ${bt.best.rps_baseline.toFixed(3)}`} />
              <Stat label="校准误差 ECE" value={bt.loto.oos_ece.toFixed(3)} hint="越接近 0 越可信" />
              <Stat label="log-loss 增益" value={`+${bt.loto.logloss_gain_vs_baseline.toFixed(3)}`} hint="相对基准" />
              <Stat label="验证规模" value={`${bt.best.n_events} 届`} hint={`${bt.best.n_matches} 场`} />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink-faint">
                    <th className="py-1.5 text-left font-normal">世界杯届（样本内明细）</th>
                    <th className="py-1.5 text-right font-normal">基准</th>
                    <th className="py-1.5 text-right font-normal">DC-Elo</th>
                    <th className="py-1.5 text-right font-normal">攻防</th>
                    <th className="py-1.5 text-right font-normal">融合</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(bt.years).map(([yr, m]) => (
                    <tr key={yr} className="border-t border-line tabular-nums">
                      <td className="py-2">{yr} 世界杯</td>
                      <td className="py-2 text-right text-ink-faint">{m.rps_baseline}</td>
                      <td className="py-2 text-right text-ink-secondary">{m.rps_dc_elo}</td>
                      <td className="py-2 text-right text-ink-secondary">{m.rps_dc_attack}</td>
                      <td className="py-2 text-right font-medium text-accent">{m.rps_ensemble}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-ink-faint">
              生产参数：时间衰减半衰期 {bt.best.half_life_days} 天，融合权重 DC-Elo {(bt.best.weight_dc_elo * 100).toFixed(0)}% /
              攻防 {(bt.best.weight_dc_attack * 100).toFixed(0)}%。
              该选择在 {Object.values(bt.loto.selected_H_counts).reduce((a, b) => a + b, 0)} 折中高度一致
              （样本外 RPS {bt.loto.oos_rps.toFixed(3)} ≈ 全量 {bt.best.pooled_rps.toFixed(3)}，说明没有过拟合）。
            </p>

            {bt.loto.reliability.length > 0 && (
              <div>
                <div className="mb-1 text-xs text-ink-faint">
                  可靠性图（{bt.best.n_events} 届样本外，点贴对角线 + 区间窄 = 概率可信）
                </div>
                <CalibrationSvg points={bt.loto.reliability.map((d) => [d.p_pred, d.freq, d.n])} />
              </div>
            )}
          </Card>
        ) : (
          <Card className="px-4 py-6">
            <p className="text-center text-sm text-ink-faint">运行 wcsim backtest --apply 后这里会显示回测对比</p>
          </Card>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">口径与局限</h2>
        <ul className="space-y-1.5 text-sm text-ink-secondary">
          <li>· Elo 随真实赛果更新；模型系数与融合权重冻结在赛前，保证概率变化只反映赛果信息。</li>
          <li>· 纯历史/Elo 口径对近年强队更敏感，可能与博彩盘略有出入。</li>
          <li>· 淘汰赛按中立场建模；小组赛对东道主本土场次计入主场优势。</li>
          <li>· 不含伤病、阵容、临场状态等模型外信息。</li>
        </ul>
      </section>
    </div>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-white/40 px-3 py-2">
      <div className="text-xs text-ink-faint">{label}</div>
      <div className="mt-0.5 text-lg font-medium tabular-nums text-accent">{value}</div>
      {hint && <div className="text-xs text-ink-faint">{hint}</div>}
    </div>
  )
}

function Prose({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-1 text-md font-medium">{title}</h3>
      <p className="text-sm leading-relaxed text-ink-secondary">{children}</p>
    </div>
  )
}
