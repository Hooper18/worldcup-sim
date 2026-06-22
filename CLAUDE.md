# worldcup-sim — 2026 世界杯比分预测与全赛程模拟

> 最后校准：2026-06-22（赛中：cron 回填至 40/104；新增赛程页 + 折线图 hover；修淘汰赛回填 bug）

## 项目概述

基于各队历史战绩（martj42 1872 年至今全部国际 A 级赛）预测 2026 美加墨世界杯每场比分，
蒙特卡洛模拟整届 104 场直到产生冠军；世界杯期间自动回填真实赛果、条件重模拟，
追踪各队夺冠概率随赛事推进的演变。

双层架构：**Python 引擎**（数据/建模/模拟，导出 JSON）+ **React 前端**（纯静态展示，Vercel 部署）。

## 技术栈

| 层 | 技术 |
|----|------|
| 引擎 | Python 3.12 + uv；numpy / pandas / scipy / requests；pytest |
| 前端 | React 18 + TS 5 + Vite 7 + Tailwind 3 + react-router-dom 6；**图表全自绘 SVG/CSS（无图表库）** |
| 数据流 | 引擎写 `web/public/data/*.json`（进 git）→ commit/push → Vercel 自动部署，无后端 |

## 目录

```
engine/
  src/wcsim/
    config.py            # 路径、数据源 URL、Elo/模型常量
    cli.py               # fetch/fit/simulate/export/update/backtest/uncertainty 子命令
    pipeline.py          # 端到端编排（抓数据→Elo→拟合→刷新赛果→条件模拟→导出）
    data/                # fetch（martj42+feed 缓存）/ normalize（双源队名归一）/ results_store
    ratings/             # elo（全历史重放自算）/ penalty（点球 Bradley-Terry）
    models/              # poisson / dc_elo / dc_attack / score_model（融合接口）/ bundle / odds（去 overround，插桩未接）
    tournament/          # structure（赛制硬数据）/ annexe_c（495 行第三名落位）/
                         #   tiebreak（2026 头对头）/ third_place / simulate（蒙特卡洛，小组+淘汰赛均代入 fixed）
    backtest/            # runner（跨赛事 LOTO CV）/ metrics（RPS/Brier/ECE/可靠性）/ baselines（Elo-logistic）
    export/writer.py     # 写 6 类前端 JSON（meta/teams/matches/groups/knockout/evolution）+ history 快照；uncertainty.json 由 pipeline 另写
  scripts/gen_static_data.py  # 一次性生成 fixtures_data.py + annexe_c_data.py（留档）
  data/                  # results.json（真实赛果状态,入库）/ params.json（拟合参数+诊断,入库）/ cache/（gitignored）
web/
  public/data/*.json     # 引擎输出（入库）
  src/                   # pages / components / hooks / lib / types
```

## 模型口径（重要）

- **融合模型**（params.json/ModelBundle）：DC-on-Elo 与纯攻防 Dixon-Coles 按比分矩阵加权融合。
  - **DC-on-Elo**：`log λ = β0 + β1·ΔElo/400 + γ·host`，DC 低比分 tau 修正，加权 MLE 4 参数。
  - **纯攻防 DC**：每队独立 att/def（解析 Poisson 梯度 + 岭正则），不依赖 Elo，提供去相关信号。
  - **融合权重由跨赛事 LOTO 回测选优**：**H=730 天、DC-Elo 0.2 / 攻防 0.8**（权重网格约束在 [0.2,0.8]，
    避免薄样本退化为单模型；20/20 折都选中 0.2 即边界解，纯攻防主导）。
- **Elo 与点球能力随真实赛果更新**；**DC β/ρ、攻防参数、H、融合权重冻结在赛前**（cutoff 2026-06-11）——只反映赛果信息。
- **点球**：Bradley-Terry 能力评分（ratings/penalty.py，强岭收缩到近 50:50；德国/阿根廷强、英格兰/荷兰弱）替代硬编码 50:50。加时 λ×1/3（martj42 无分时段数据，保留理论值）。
- **淘汰赛按中立场**（忽略东道主本土加成）；小组赛照常加 host。
- 赛前（冻结模型）夺冠基线：阿根廷 ~17.8% / 西班牙 ~16.5% / 英格兰 ~8.4%。**赛中实时值见线上**（随 cron 回填变化，6/22 约阿根廷 19% / 西班牙 15%）。

### 科学性强化（2026-06-12 第二轮）
- **回测 = 跨赛事 LOTO 交叉验证**：2014 年以来世界杯/欧洲杯/美洲杯/非洲杯/亚洲杯 20 届 895 场；
  每折 (H,权重) 只在其余赛事选、留出赛事样本外评估（修掉旧版同集选参+评估的泄漏）。
  样本外 RPS 0.189 ≈ 全量 0.188（无过拟合）；H=730 中 17/20 折、权重 0.2 中 20/20 折（稳定）。
- **诚实基准**：Elo-logistic 两参数简单模型 RPS 0.192——融合模型 0.189 只小幅领先（不是 climatology 0.229 的虚高对照）。
- **校准**：Brier/ECE/Wilson 可靠性图；样本外 ECE 0.019（已很校准）。
- **参数不确定性**：`wcsim uncertainty` bootstrap → 夺冠概率置信区间（阿根廷 17.8% 实为 [9.3%,23.5%]）；
  写 uncertainty.json，update 在有新赛果时刷新；前端夺冠条叠 95% 误差带。
- **常数数据驱动**：dc_attack 的 RIDGE 经时序 CV 选定（0.005，模型对该值不敏感）；经验主场优势验证 Elo +100。
  注：penalty.py 另有独立 RIDGE=3.0（硬编码、非 CV 选，勿与攻防 ridge 混淆）。
- **赔率机械**：models/odds.py 去 overround（proportional/power/Shin）+ logit 共识，留插桩；
  **默认不接实时赔率**（免费稳定的国家队大赛历史 1X2 赔率源不存在，不把脆弱爬虫塞进 cron）。
- `wcsim backtest --apply`（约数分钟）重跑回测+选参重拟合；`wcsim uncertainty` 算区间。

## 赛制（已多源核验，写死进 structure.py / annexe_c.py）

48 队 12 组每组单循环 72 场 → 每组前 2 + 8 个最佳第三进 32 强 → 16/8/4 强 + 季军 + 决赛 = 104 场。
小组 tiebreaker **2026 新规头对头优先**：相互积分→相互净胜→相互进球→子集递归→总净胜→
总进球→行为分→FIFA 排名（模拟中以赛前 Elo 代理，行为分不可得故跳过）。
8 个第三名落位由 FIFA 规程 Annexe C 的 495 行查找表决定（C(12,8) 全覆盖，import 时校验零违规）。

## 数据源

- 历史比赛：`martj42/international_results` raw CSV（CC0，每日 commit，已含 2026 赛程行赛后回填）
- 赛程/赛果：`fixturedownload.com/feed/json/fifa-world-cup-2026`（免 key，**需浏览器 UA 否则 403**）；feed 为生产唯一赛果源（results_store.parse_feed），parse_martj42 为未接的回退
- Elo 交叉校验：`eloratings.net/World.tsv`（有 fetcher 但无 loader，当前未接入，仅留档）
- 队名归一：martj42 与 feed 两套拼写各一张表（normalize.py），未知队名一律 raise

## 常用命令

```bash
# 引擎（engine/ 下；本机用 python -m uv run ...，因 uv 不在 PATH）
uv run wcsim fit                 # 拟合（赛前一次性，落 params.json）
uv run wcsim export -n 100000    # 模拟 + 导出 JSON
uv run wcsim update -n 100000    # 一条龙：刷新赛果→有新完赛才重模拟→导出（cron 用）
uv run pytest                    # 101 用例

# 前端（web/ 下）
npm run dev / test / build
```

## 测试

引擎 101 用例（structure/annexe_c/normalize/results_store/elo/penalty/poisson/odds_baseline/dc_fit/dc_attack/tiebreak/simulate/export）；
前端 vitest 7 用例 + Playwright smoke 5 用例（page.route stub data，测真实构建产物）。CI 双 job 全绿。

## 坑位

- **Windows 本地**：所有 `open` 显式 `encoding='utf-8'`；PowerShell/bash 跑 Python 设 `PYTHONIOENCODING=utf-8`；
  `python -m uv`（uv 装在 site Scripts 不在 PATH）。
- **日期**：kickoff 全存 UTC，前端 `format.ts` 按本地时区显示，**禁用 toISOString 切日期**。
- **JSON 导出**：`ensure_ascii=False` + `newline='\n'`；.gitattributes 强制 LF。
- 母仓 `.gitignore` 已登记 `worldcup-sim/` 为嵌套独立仓。
- **本地常落后 cron**：远端每天 5 班 cron 直推 main 回填数据。本地开工先 `git pull --ff-only`；
  push 撞车时 `git pull --rebase`（代码改动与数据文件不冲突，rebase 即可），勿强推。

## 部署

- 独立仓 `Hooper18/worldcup-sim`，Vercel 项目 root=`web/`，子域名走 Cloudflare CNAME→vercel-dns。
- **worldcup.tuchenguang.com 已上线**；push main → Vercel 自动部署已验证。
- 数据更新 = cron 跑 `wcsim update` + commit `web/public/data/` + push → 自动部署。

## 进度

- **M0 + M1 已上线**（2026-06-12）：引擎全链路（数据→Elo→DC-on-Elo+纯攻防融合→蒙特卡洛→JSON）+ 前端 +
  GitHub Actions CI（双 job）+ 自动回填 cron（5 班）+ Vercel/Cloudflare 域名。
- **赛中迭代（2026-06-21/22）**：
  - cron 持续回填，当前 **40/104**（小组赛进行中）。
  - 新增第 7 页 `/schedule` 赛程页：全 104 场按阶段/日期时间轴 + 真实比分 + 阶段筛选 +
    淘汰赛对阵位中文描述 + 顶部「每打一场夺冠率走势」折线图（按 matches_played 去重）。
  - 折线图加 hover：竖直参考线 + 各队该场次具体数值（概率演变页与赛程页共用 LineChartSvg）。
  - **修淘汰赛回填 bug**：simulate.play() 对已完赛淘汰赛代入真实赛果（此前只小组赛生效，淘汰赛仍抽样），
    新增 2 回归测试（普通比分 + 点球），进淘汰赛后生效。
- **前端 7 页**：仪表盘 / 赛程 / 小组（总览+详情）/ 对阵树 / 单场详情 / 概率演变 / 模型说明。
- **可选增强（未做）**：历史快照浏览页、XGBoost 第三模型、实时赔率融合、FIFA 排名字段、暗色模式、移动端打磨；
  引擎清死代码（eloratings fetcher / PENALTY_WIN_PROB / FIT_WINDOW_YEARS / parse_martj42 / 前端 Placeholder.tsx / teams.flag emoji）；
  backtest 的 dc_attack.fit 未传 ridge（用默认 0.02，生产 0.005，影响小）。
