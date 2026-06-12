import { test, expect, type Page } from '@playwright/test'

// 用固定 fixture stub /data/*.json，smoke 不依赖真实数据文件（避免数据漂移导致 flaky）。
const TEAMS = {
  ESP: { name_zh: '西班牙', name_en: 'Spain', group: 'H', flag: '🇪🇸', elo: 2200, fifa_rank: 1, host: false },
  MEX: { name_zh: '墨西哥', name_en: 'Mexico', group: 'A', flag: '🇲🇽', elo: 1950, fifa_rank: 12, host: true },
  RSA: { name_zh: '南非', name_en: 'South Africa', group: 'A', flag: '🇿🇦', elo: 1600, fifa_rank: 60, host: false },
  KOR: { name_zh: '韩国', name_en: 'Korea Republic', group: 'A', flag: '🇰🇷', elo: 1820, fifa_rank: 22, host: false },
  CZE: { name_zh: '捷克', name_en: 'Czechia', group: 'A', flag: '🇨🇿', elo: 1780, fifa_rank: 36, host: false },
}

const FORECAST = {
  p_home: 0.5, p_draw: 0.27, p_away: 0.23, lambda_home: 1.6, lambda_away: 0.9,
  top_scores: [{ h: 1, a: 0, p: 0.14 }, { h: 1, a: 1, p: 0.1 }],
  score_matrix: Array.from({ length: 6 }, () => Array.from({ length: 6 }, () => 0.02)),
}

const META = {
  run_id: '20260612T0000Z', generated_at: '2026-06-12T00:00:00Z', n_sims: 100000, matches_played: 1,
  data: { martj42_rows: 49477, elo_through: '2026-06-11', results_count: 1 },
  models: {
    components: [
      { id: 'dc_elo', name_zh: 'DC-on-Elo（x）', weight: 0.3, params: {} },
      { id: 'dc_attack', name_zh: '纯攻防 Dixon-Coles', weight: 0.7, params: {} },
    ],
    half_life_days: 730,
    backtest: {
      best: { half_life_days: 730, weight_dc_elo: 0.2, weight_dc_attack: 0.8, pooled_rps: 0.188, oos_rps: 0.189, rps_baseline: 0.229, rps_elo_baseline: 0.192, n_events: 20, n_matches: 895 },
      years: { '2018': { n_matches: 64, rps_baseline: 0.243, rps_elo_baseline: 0.205, rps_dc_elo: 0.213, rps_dc_attack: 0.2, rps_ensemble: 0.202, logloss_dc_elo: 0.95, calibration: [[0.1, 0.09, 50], [0.5, 0.52, 30]] } },
      loto: { oos_rps: 0.189, oos_logloss: 0.93, oos_brier: 0.57, oos_ece: 0.02, climatology_rps: 0.229, elo_baseline_rps: 0.192, logloss_gain_vs_elo: 0.01, n_folds: 20, n_matches: 895, reliability: [{ p_pred: 0.1, freq: 0.09, ci_lo: 0.06, ci_hi: 0.12, n: 50 }, { p_pred: 0.5, freq: 0.52, ci_lo: 0.45, ci_hi: 0.59, n: 30 }], selected_H_counts: { '730': 17, '1095': 3 }, selected_w_counts: { '0.2': 20 } },
    },
  },
}

const MATCHES = [
  { id: 1, stage: 'group', group: 'A', kickoff_utc: '2026-06-11T19:00:00Z', venue: 'Mexico City Stadium', status: 'finished', result: { h: 2, a: 0, after: 'FT' }, home: 'MEX', away: 'RSA', forecast: FORECAST, model_breakdown: { dc_elo: { p_home: 0.6, p_draw: 0.25, p_away: 0.15 }, dc_attack: { p_home: 0.55, p_draw: 0.28, p_away: 0.17 } } },
  { id: 2, stage: 'group', group: 'A', kickoff_utc: '2026-06-12T02:00:00Z', venue: 'Guadalajara Stadium', status: 'scheduled', result: null, home: 'KOR', away: 'CZE', forecast: FORECAST, model_breakdown: { dc_elo: { p_home: 0.4, p_draw: 0.3, p_away: 0.3 }, dc_attack: { p_home: 0.42, p_draw: 0.29, p_away: 0.29 } } },
  { id: 73, stage: 'r32', group: null, kickoff_utc: '2026-06-28T19:00:00Z', venue: 'Los Angeles Stadium', status: 'scheduled', result: null, home: '2A', away: '2B', slot_dist: { home: [{ team: 'KOR', p: 0.33 }], away: [{ team: 'MEX', p: 0.4 }] } },
]

const GROUPS = {
  A: {
    MEX: { p_rank: [0.5, 0.3, 0.15, 0.05], p_top2: 0.8, p_third_advance: 0.1, p_advance: 0.9, exp_pts: 6, exp_gd: 2, current: { pts: 3, gd: 2, gf: 2, played: 1 } },
    RSA: { p_rank: [0.05, 0.15, 0.3, 0.5], p_top2: 0.2, p_third_advance: 0.1, p_advance: 0.3, exp_pts: 2, exp_gd: -2, current: { pts: 0, gd: -2, gf: 0, played: 1 } },
    KOR: { p_rank: [0.3, 0.3, 0.25, 0.15], p_top2: 0.6, p_third_advance: 0.15, p_advance: 0.75, exp_pts: 4, exp_gd: 0, current: null },
    CZE: { p_rank: [0.15, 0.25, 0.3, 0.3], p_top2: 0.4, p_third_advance: 0.12, p_advance: 0.52, exp_pts: 3, exp_gd: 0, current: null },
  },
}

const KNOCKOUT = {
  teams: Object.fromEntries(Object.keys(TEAMS).map((c) => [c, { p_r32: 0.8, p_r16: 0.5, p_qf: 0.3, p_sf: 0.2, p_final: 0.1, p_champion: 0.05 }])),
  bracket: { '73': { home_slot: '2A', away_slot: '2B' } },
}

const EVOLUTION = {
  snapshots: [
    { run_id: 'a', at: '2026-06-11T00:00:00Z', matches_played: 0 },
    { run_id: 'b', at: '2026-06-12T00:00:00Z', matches_played: 1 },
  ],
  teams: Object.fromEntries(Object.keys(TEAMS).map((c) => [c, { champion: [0.05, 0.06], final: [0.1, 0.11], sf: [0.2, 0.21], advance: [0.8, 0.82] }])),
}

async function stubData(page: Page) {
  const map: Record<string, unknown> = {
    'meta.json': META, 'teams.json': TEAMS, 'matches.json': MATCHES,
    'groups.json': GROUPS, 'knockout.json': KNOCKOUT, 'evolution.json': EVOLUTION,
  }
  await page.route('**/data/*.json', (route) => {
    const name = route.request().url().split('/').pop()!
    route.fulfill({ json: map[name] ?? {} })
  })
}

test.beforeEach(async ({ page }) => stubData(page))

test('仪表盘渲染夺冠概率与赛程', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('夺冠概率')).toBeVisible()
  await expect(page.getByText('西班牙').first()).toBeVisible()
})

test('小组页显示混合真实/期望积分', async ({ page }) => {
  await page.goto('/groups/A')
  await expect(page.getByText('A 组').first()).toBeVisible()
  await expect(page.getByText('墨西哥').first()).toBeVisible()
})

test('对阵树渲染未定槽位的最可能球队', async ({ page }) => {
  await page.goto('/bracket')
  await expect(page.getByText('32 强').first()).toBeVisible()
})

test('单场详情显示赛前预测与真实比分', async ({ page }) => {
  await page.goto('/match/1')
  await expect(page.getByText('2 : 0')).toBeVisible()
  await expect(page.getByText('赛前预测')).toBeVisible()
})

test('模型页显示回测对比表', async ({ page }) => {
  await page.goto('/model')
  await expect(page.getByText('回测验证')).toBeVisible()
  await expect(page.getByText('融合').first()).toBeVisible()
  await expect(page.getByText('样本外 RPS').first()).toBeVisible() // LOTO 诚实指标卡
  await expect(page.getByText('0.202')).toBeVisible() // 2018 融合 RPS
})
