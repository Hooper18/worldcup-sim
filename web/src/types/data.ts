// 与 engine/export/writer.py 的 JSON schema 一一对应（手写，引擎侧 pytest 校验字段）

export type Stage = 'group' | 'r32' | 'r16' | 'qf' | 'sf' | 'third' | 'final'

export interface BacktestYear {
  n_matches: number
  rps_baseline: number
  rps_dc_elo: number
  rps_dc_attack: number
  rps_ensemble: number
  logloss_dc_elo: number
  calibration: number[][] // [[平均预测, 经验频率, 样本数], ...]
}
export interface Backtest {
  best: { half_life_days: number; weight_dc_elo: number; weight_dc_attack: number; combined_rps: number }
  years: Record<string, BacktestYear>
}

export interface Meta {
  run_id: string
  generated_at: string
  n_sims: number
  matches_played: number
  data: { martj42_rows: number; elo_through: string; results_count: number }
  models: {
    components: { id: string; name_zh: string; weight: number; params: Record<string, number | string> }[]
    half_life_days: number
    backtest: Backtest | Record<string, never>
  }
}

export interface Team {
  name_zh: string
  name_en: string
  group: string
  flag: string
  elo: number
  fifa_rank: number | null
  host: boolean
}
export type Teams = Record<string, Team>

export interface MatchResult {
  h: number
  a: number
  after: 'FT' | 'AET' | 'PEN'
  pen_winner?: 'home' | 'away'
}

export interface Forecast {
  p_home: number
  p_draw: number
  p_away: number
  lambda_home: number
  lambda_away: number
  top_scores: { h: number; a: number; p: number }[]
  score_matrix: number[][]
}

export interface SlotDist {
  home: { team: string; p: number }[]
  away: { team: string; p: number }[]
}

export interface Match {
  id: number
  stage: Stage
  group: string | null
  kickoff_utc: string
  venue: string
  status: 'scheduled' | 'finished'
  result: MatchResult | null
  home: string | null
  away: string | null
  forecast?: Forecast
  slot_dist?: SlotDist
  model_breakdown?: Record<string, { p_home: number; p_draw: number; p_away: number }>
}

export interface GroupTeam {
  p_rank: number[]
  p_top2: number
  p_third_advance: number
  p_advance: number
  exp_pts: number
  exp_gd: number
  current: { pts: number; gd: number; gf: number; played: number } | null
}
export type Groups = Record<string, Record<string, GroupTeam>>

export interface KnockoutTeam {
  p_r32: number
  p_r16: number
  p_qf: number
  p_sf: number
  p_final: number
  p_champion: number
}
export interface Knockout {
  teams: Record<string, KnockoutTeam>
  bracket: Record<string, { home_slot?: string; away_slot?: string; home_src?: string; away_src?: string }>
}

export interface Evolution {
  snapshots: { run_id: string; at: string; matches_played: number }[]
  teams: Record<string, { champion: number[]; final: number[]; sf: number[]; advance: number[] }>
}
