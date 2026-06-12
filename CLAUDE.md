# worldcup-sim — 2026 世界杯比分预测与全赛程模拟

> 最后校准：2026-06-12（项目创建，M0 完成）

## 项目概述

基于各队历史战绩（martj42 1872 年至今全部国际 A 级赛）预测 2026 美加墨世界杯每场比分，
蒙特卡洛模拟整届 104 场直到产生冠军；世界杯期间自动回填真实赛果、条件重模拟，
追踪各队夺冠概率随赛事推进的演变。

双层架构：**Python 引擎**（数据/建模/模拟，导出 JSON）+ **React 前端**（纯静态展示，Vercel 部署）。

## 技术栈

| 层 | 技术 |
|----|------|
| 引擎 | Python 3.12 + uv；numpy / pandas / scipy / requests；pytest |
| 前端 | React 18 + TS 5 + Vite 7 + Tailwind 3 + react-router-dom 6；recharts（M1 演变页用） |
| 数据流 | 引擎写 `web/public/data/*.json`（进 git）→ commit/push → Vercel 自动部署，无后端 |

## 目录

```
engine/
  src/wcsim/
    config.py            # 路径、数据源 URL、Elo/模型常量
    cli.py               # fetch/fit/simulate/export/update/backtest 子命令
    pipeline.py          # 端到端编排（抓数据→Elo→拟合→刷新赛果→条件模拟→导出）
    data/                # fetch（martj42+feed 缓存）/ normalize（双源队名归一）/ results_store
    ratings/elo.py       # 全历史重放自算 Elo
    models/              # poisson（比分矩阵+DC tau）/ dc_elo（加权 MLE 主模型）
    tournament/          # structure（赛制硬数据）/ annexe_c（495 行第三名落位）/
                         #   tiebreak（2026 头对头）/ third_place / simulate（蒙特卡洛）
    export/writer.py     # 写 7 类 JSON
  scripts/gen_static_data.py  # 一次性生成 fixtures_data.py + annexe_c_data.py（留档）
  data/                  # results.json（真实赛果状态,入库）/ params.json（拟合参数,入库）/ cache/（gitignored）
web/
  public/data/*.json     # 引擎输出（入库）
  src/                   # pages / components / hooks / lib / types
```

## 模型口径（重要）

- **融合模型**（params.json/ModelBundle）：DC-on-Elo 与纯攻防 Dixon-Coles 按比分矩阵加权融合。
  - **DC-on-Elo**：`log λ = β0 + β1·ΔElo/400 + γ·host`，DC 低比分 tau 修正，加权 MLE 4 参数。
  - **纯攻防 DC**：每队独立 att/def（解析 Poisson 梯度 + 岭正则），不依赖 Elo，提供去相关信号。
  - **融合权重由 2018/2022 回测选优**：当前 H=1095 天、DC-Elo 0.3 / 攻防 0.7（约束在 [0.3,0.7]
    避免 128 场薄样本退化为单模型）。两模型回测 RPS 均优于基准（0.243→0.20/0.21）。
- **Elo 随真实赛果更新**（每次重放到最新完赛）；**DC β/ρ、攻防参数、H、融合权重冻结在赛前**——
  保证概率演变只反映赛果信息。
- 融合后夺冠：西班牙 17.6% / 阿根廷 14.9% / 英格兰 9.6% / 法国 8.4%（比纯 Elo 更贴近博彩共识）。
- **淘汰赛按中立场**（忽略东道主本土加成）；小组赛照常加 host。
- `wcsim backtest --apply` 重跑回测并用最优参数重拟合。

## 赛制（已多源核验，写死进 structure.py / annexe_c.py）

48 队 12 组每组单循环 72 场 → 每组前 2 + 8 个最佳第三进 32 强 → 16/8/4 强 + 季军 + 决赛 = 104 场。
小组 tiebreaker **2026 新规头对头优先**：相互积分→相互净胜→相互进球→子集递归→总净胜→
总进球→行为分→FIFA 排名（模拟中以赛前 Elo 代理，行为分不可得故跳过）。
8 个第三名落位由 FIFA 规程 Annexe C 的 495 行查找表决定（C(12,8) 全覆盖，import 时校验零违规）。

## 数据源

- 历史比赛：`martj42/international_results` raw CSV（CC0，每日 commit，已含 2026 赛程行赛后回填）
- 赛程/赛果：`fixturedownload.com/feed/json/fifa-world-cup-2026`（免 key，**需浏览器 UA 否则 403**）
- Elo 交叉校验：`eloratings.net/World.tsv`
- 队名归一：martj42 与 feed 两套拼写各一张表（normalize.py），未知队名一律 raise

## 常用命令

```bash
# 引擎（engine/ 下；本机用 python -m uv run ...，因 uv 不在 PATH）
uv run wcsim fit                 # 拟合（赛前一次性，落 params.json）
uv run wcsim export -n 100000    # 模拟 + 导出 JSON
uv run wcsim update -n 100000    # 一条龙：刷新赛果→有新完赛才重模拟→导出（cron 用）
uv run pytest                    # 78 用例

# 前端（web/ 下）
npm run dev / test / build
```

## 测试

引擎 85 用例（structure/annexe_c/normalize/results_store/elo/poisson/dc_fit/dc_attack/tiebreak/simulate/export）；
前端 vitest 7 用例 + Playwright smoke 5 用例（page.route stub data，测真实构建产物）。CI 双 job 全绿。

## 坑位

- **Windows 本地**：所有 `open` 显式 `encoding='utf-8'`；PowerShell 跑 Python 设 `$env:PYTHONIOENCODING='utf-8'`；
  `python -m uv`（uv 装在 site Scripts 不在 PATH）。
- **日期**：kickoff 全存 UTC，前端 `format.ts` 按本地时区显示，**禁用 toISOString 切日期**。
- **JSON 导出**：`ensure_ascii=False` + `newline='\n'`；.gitattributes 强制 LF。
- 母仓 `.gitignore` 已登记 `worldcup-sim/` 为嵌套独立仓。

## 部署

- 独立仓 `Hooper18/worldcup-sim`，Vercel 项目 root=`web/`，子域名走 Cloudflare CNAME→vercel-dns。
- 数据更新 = 重跑 `wcsim update` + commit `web/public/data/` + push → Vercel 自动部署。

## 进度

- **M0 + M1 完成**（2026-06-12）：
  - 引擎全链路：数据管道 → Elo → DC-on-Elo + 纯攻防双模型融合 → 蒙特卡洛 → 7 类 JSON
  - 前端 6 页：仪表盘 / 小组（总览+详情）/ 对阵树 / 单场详情 / 概率演变 / 模型说明
  - 2018/2022 回测选优；GitHub Actions CI（双 job）+ 自动回填 cron（5 班）
  - 揭幕战墨西哥 2-0 南非已回填条件化；首版预测已生成
  - GitHub: https://github.com/Hooper18/worldcup-sim
- **待用户操作**：Vercel 导入仓库（root=`web/`）+ Cloudflare 子域名 CNAME。
- **赛中可选增强**：历史快照浏览页、XGBoost 第三模型、API-Football 实时比分条、FIFA 排名字段。
