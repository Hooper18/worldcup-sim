# worldcup-sim — 2026 世界杯比分预测与全赛程模拟

> 最后校准：2026-06-25（赛中：cron 回填至 48/104；2026-06-25 完成一轮「大而全」多智能体自我审查——无正确性/泄漏硬伤，详见进度末；Tier-3 = XGBoost 只读评估 + 实时赔率融合「机制就绪但默认关」）

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
    cli.py               # fetch/fit/simulate/export/update/backtest/uncertainty/performance/gbm-eval/odds-preview 子命令
    pipeline.py          # 端到端编排（抓数据→Elo→拟合→刷新赛果→条件模拟→导出）
    data/                # fetch（martj42+feed 缓存）/ normalize（双源队名归一）/ results_store
    ratings/             # elo（全历史重放自算）/ penalty（点球 Bradley-Terry）
    models/              # poisson / dc_elo / dc_attack / score_model（融合接口）/ bundle /
                         #   odds（去 overround + 共识 + 1X2 融合机械）/ odds_feed（the-odds-api 适配器，env 门控默认关）
    tournament/          # structure（赛制硬数据）/ annexe_c（495 行第三名落位）/
                         #   tiebreak（2026 头对头）/ third_place / simulate（蒙特卡洛，小组+淘汰赛均代入 fixed）
    backtest/            # runner（跨赛事 LOTO CV）/ metrics（RPS/Brier/ECE/可靠性 + 配对 bootstrap 显著性）/
                         #   baselines（Elo-logistic）/ gbm（XGBoost 只读评估臂，可选依赖 ml，不进生产）
    backtest/performance.py  # 本届实战表现：重建赛前预测对赛果打分 → performance.json
    export/writer.py     # 写 6 类前端 JSON（meta/teams/matches/groups/knockout/evolution）+ history 快照；uncertainty.json / performance.json 由 pipeline 另写
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
- **赔率机械（实时赔率融合：机制就绪但默认关）**：models/odds.py 去 overround（proportional/power/Shin）
  + logit 共识 + `blend_with_market`（1X2 层融合）；models/odds_feed.py = the-odds-api v4 适配器
  （env `ODDS_API_KEY` 门控、**默认关、不进 cron**、失败不静默回退）。`wcsim odds-preview` 只读并排打印
  模型/市场/融合。**诚实边界**：没有稳定免费的国家队大赛历史 1X2 赔率源（the-odds-api 历史付费 + 10x 倍率、
  football-data.co.uk 只含俱乐部、Kaggle martj42 只有比分）→ 融合权重无法进 LOTO 回测、未经验证；
  **绝不碰线上预测/params.json/ECE**（match_forecast 只并列写 market/blended，主 1X2 永远是纯统计模型）。
- **XGBoost 第三模型（只读评估，不进生产）**：backtest/gbm.py 仿 baselines 的 fit/probs，`wcsim gbm-eval`
  并排比 GBM/Elo 基准/融合的 LOTO 样本外 RPS + 配对 bootstrap CI。实跑结论（21 届/939 场）：GBM 0.1934
  与 Elo 基准 0.1914 无显著差异、显著劣于融合 0.1877（ΔCI 排除 0）→ 净增益不可测、且只出 1X2 进不了
  比分矩阵融合，故 production 不接、params.json 不动。xgboost 为可选依赖 `ml`（CI 不装、测试 importorskip 跳过）。
- `wcsim backtest --apply`（约数分钟）重跑回测+选参重拟合；`wcsim uncertainty` 算区间。

## 赛制（已多源核验，写死进 structure.py / annexe_c.py）

48 队 12 组每组单循环 72 场 → 每组前 2 + 8 个最佳第三进 32 强 → 16/8/4 强 + 季军 + 决赛 = 104 场。
小组 tiebreaker **2026 新规头对头优先**：相互积分→相互净胜→相互进球→子集递归→总净胜→
总进球→行为分→FIFA 排名（模拟中以赛前 Elo 代理，行为分不可得故跳过）。
8 个第三名落位由 FIFA 规程 Annexe C 的 495 行查找表决定（C(12,8) 全覆盖，import 时校验零违规）。

## 数据源

- 历史比赛：`martj42/international_results` raw CSV（CC0，每日 commit，已含 2026 赛程行赛后回填）
- 赛程/赛果：`fixturedownload.com/feed/json/fifa-world-cup-2026`（免 key，**需浏览器 UA 否则 403**）；feed 为生产唯一赛果源（results_store.parse_feed），parse_martj42 为未接的回退
- Elo：由 martj42 历史全量重放自算（ratings/elo.py），无外部 Elo 数据源（原 eloratings 抓取已移除）
- 队名归一：martj42 与 feed 两套拼写各一张表（normalize.py），未知队名一律 raise

## 常用命令

```bash
# 引擎（engine/ 下；本机用 python -m uv run ...，因 uv 不在 PATH）
uv run wcsim fit                 # 拟合（赛前一次性，落 params.json）
uv run wcsim export -n 100000    # 模拟 + 导出 JSON
uv run wcsim update -n 100000    # 一条龙：刷新赛果→有新完赛才重模拟→导出（cron 用）
uv run --extra ml wcsim gbm-eval # XGBoost 只读评估（需 ml 可选依赖；不改 params.json）
ODDS_API_KEY=… uv run wcsim odds-preview  # 只读预览市场共识与融合（默认关、不进 cron）
uv run pytest                    # 130 用例（gbm 5 例需 ml，无 xgboost 时 importorskip 跳过）

# 前端（web/ 下）
npm run dev / test / build
```

## 测试

引擎 130 用例（structure/annexe_c/normalize/results_store/elo/penalty/poisson/odds_baseline/odds_feed/gbm/dc_fit/dc_attack/tiebreak/simulate/export/performance/pipeline）；
其中 gbm 5 例需可选依赖 `ml`（无 xgboost 时 `pytest.importorskip` 跳过，CI 不装故跳过）。
前端 vitest 16 用例（+InfoTip 术语弹窗 3）+ Playwright smoke 7 用例（page.route stub data，测真实构建产物）。CI 双 job 全绿。

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
  - cron 持续回填，当前 **48/104**（小组赛进行中）。
  - 新增第 7 页 `/schedule` 赛程页：全 104 场按阶段/日期时间轴 + 真实比分 + 阶段筛选 +
    淘汰赛对阵位中文描述 + 顶部「每打一场夺冠率走势」折线图（按 matches_played 去重）。
  - 折线图加 hover：竖直参考线 + 各队该场次具体数值（概率演变页与赛程页共用 LineChartSvg）。
  - **修淘汰赛回填 bug**：simulate.play() 对已完赛淘汰赛代入真实赛果（此前只小组赛生效，淘汰赛仍抽样），
    新增 2 回归测试（普通比分 + 点球），进淘汰赛后生效。
  - **技术债大清理**：引擎接 ruff、前端接 ESLint+Prettier+knip 全进 CI（永久拦新债）；清死代码
    （PENALTY_WIN_PROB / eloratings 抓取 / Placeholder.tsx / teams.flag emoji / BracketView 死 prop）；
    backtest ridge 改 select_ridge→fit 与生产一致。测试 引擎 107 / 前端 vitest 13 / Playwright 6。
  - **Tier-1 本届实战表现**：`backtest/performance.py` 用冻结 bundle + 重放到赛前的 Elo
    （replay with_history 取 home_elo_pre）重建每场赛前融合 1X2，对真实赛果算 RPS/Brier/命中率，
    vs Elo-logistic + climatology → `performance.json`（接 pipeline.export + `wcsim performance`）。
    当前 44/48 场（4 场待 martj42 落赛前 Elo 暂跳过）：融合 RPS **0.162** / 命中率 **56.8%** 优于 Elo 0.182、climatology 0.218。
    ModelPage 加「本届实战表现」面板（指标卡 + 累计 RPS 三线），MatchDetail 已完赛加「赛后复盘」（赛前预测 vs 实际 + 命中）。
  - **cron 健壮性**：build_context 不再静默吞 feed 失败（记 refresh_failed + data.feed_ok），
    `wcsim update` 遇 feed 失败发 `::error::` + 非零退出，cron 变红可见。
  - **暗色模式**：色板改 CSS 变量（RGB 三通道，`rgb(var / <alpha-value>)`），tailwind `darkMode:'class'`；
    亮=暖白 / 暗=ChatGPT 风 #212121；AppShell 日/月切换 + localStorage 持久化 + index.html 无闪烁脚本；
    图表硬编码 hex 全改 `rgb(var(--c-*))`（var() 在 SVG presentation 属性可解析）。`bg-white/40`→`bg-card/40`。
  - **移动端响应式导航**：标题/切换固定，6 项导航窄屏横向可滚（隐藏滚动条），375px 全页零横向溢出。
  - **淘汰赛纳入实战评分（前瞻）**：`parse_feed` 给淘汰赛 Result 增记实际队码 home/away；
    `performance.py` 统一评小组（MATCHES 码+主场）+淘汰赛（store 码+中立场），开赛后自动生效。
  - **Tier-3（2026-06-24，引擎 108→126 测试、CI 绿、两件独立 commit）**：
    - **XGBoost 第三模型「只读评估」**（backtest/gbm.py + `wcsim gbm-eval`）：go/no-go 已定生产不加，
      只做只读评估。metrics 补 `paired_bootstrap_rps_diff`（repo 此前缺 RPS 显著性工具）。实跑 21 届/939 场：
      GBM 0.1934 与 Elo 基准 0.1914 无显著差异、显著劣于融合 0.1877（ΔCI 排除 0）→ 净增益不可测、
      只出 1X2 进不了比分矩阵融合，params.json 一行不动；xgboost 为可选依赖 `ml`。
    - **实时赔率融合「机制就绪但默认关」**（models/odds_feed.py 适配器 + odds.blend_with_market +
      match_forecast 并列 market/blended + `wcsim odds-preview`）：env `ODDS_API_KEY` 门控、默认关、不进 cron、
      绝不碰线上预测/params.json/ECE。诚实边界：无稳定免费的国家队历史 1X2 赔率源 → 融合权重无法回测、未经验证。
  - **术语小词典（面向球迷，2026-06-24）**：`lib/glossary.ts` 集中维护 Elo/RPS/ECE/泊松/Dixon-Coles/
    蒙特卡洛/留一届交叉验证/bootstrap 等的大白话解释，`components/InfoTip.tsx` 行内「ⓘ」点开弹出
    （点按/Esc/点外关闭、CSS 变量主题感知、role=tooltip 无障碍）；接入 ModelPage/Dashboard/MatchDetail。
    以后新增术语只改 glossary.ts，别在页面里散写解释。
  - **大而全自我审查（2026-06-25，多智能体 fan-out + 对抗复核）**：结论——建模（dc_elo/dc_attack/poisson/score_model/ensemble）、模拟器（simulate 小组+淘汰赛 fixed 代入/加时/点球 BT）、赛制（2026 头对头 tiebreak、annexe_c 含 import 期 495 键校验）、数据管线、回测 LOTO、实战评分 performance.py **无正确性或数据泄漏硬伤**；「诚实优先」叙事经核查成立（performance 用赛前 `home_elo_pre` 重建、baselines 只在 `hist_cut` 拟合、LOTO 仅在其余赛事选 H/权重、metrics RPS/Brier/ECE/Wilson/配对 bootstrap 口径正确）。**顺手修（各独立 commit）**：① baselines sigmoid→`scipy.expit` 消 overflow 警告；② odds_feed 异常日志只记类型，杜绝 `ODDS_API_KEY` 经 requests 异常 URL 进日志（兑现模块「绝不进日志」承诺）；③ useData 失败时清理 inflight（修瞬时网络抖动后该数据键永久卡 rejected promise、无法重试）；④ 文档 drift（fetch 删 eloratings、cli 子命令补全、实战场次）。**第二批已做（6 独立 commit `2d96ffb..bab676a`，引擎 126→130 测试）**：odds `deoverround_power` 根失败回退 + `blend_with_market` weight 夹 [0,1]；点球 BT 抽成 `penalty_home_prob`+单调/对称测试；抽 `refresh_results_from_feed`+cron feed 失败 3 例回归测试；删 `TeamLabel` 死 prop `showFlag`；折线图调色板改 CSS 变量 `--chart-1..6` 暗色自适应（蓝 #3a5a8c→#6e9bd6 等深底变亮）+ `ink-faint` 对比度↑(2.7→~4:1 AA-Large)；**`InfoTip` 弹层改 portal+fixed 定位**（preview 实测最右收到 right=367 / 最左 left=8 零裁切、escape `overflow-x-auto` 表格）+ ⓘ 触达扩到 26px + 描边字色 `ink-faint`→`ink-secondary`。**仍未做（低优先/需实测/需方向）**：淘汰赛 AET 比分 label 失真与「赛果被修正不触发重模拟」（待淘汰赛首日 ~6/28 真数据实测）、tiebreak 同分回落的 Python 热循环向量化（结果正确、纯性能、改动有回归风险）、几处 P2 前端打磨（页面缺 `<h1>` 层级、ScoreHeatGrid 硬编码 `#fff`、移动端导航无滚动提示、History 滑块 focus 环、跨页图例/排序去重）。
- **前端 8 页**：仪表盘 / 赛程 / 小组（总览+详情）/ 对阵树 / 单场详情（含赛后复盘）/ 概率演变 / 模型说明（含本届实战表现）/ 历史回放。
- **可选增强（剩余未做）**：XGBoost 进生产（已评估否决，仅留只读臂）、实时赔率付费历史回测、FIFA 排名字段。
