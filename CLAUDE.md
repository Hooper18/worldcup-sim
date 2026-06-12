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

- **主模型 DC-on-Elo**：`log λ = β0 + β1·ΔElo/400 + γ·host`，Dixon-Coles 低比分 tau 修正，
  近 8 年加权 MLE（时间衰减半衰期 730 天 × 赛事 K 权重），scipy L-BFGS-B 4 参数。
  当前拟合：β0=0.10 β1=0.73 γ=0.23 ρ=-0.043（params.json）。
- **Elo**：随真实赛果更新（每次重放到最新完赛）。
- **DC 参数 β/ρ/H 冻结在赛前拟合值**——一届几十场重拟只引噪声；冻结保证概率演变曲线
  只反映赛果信息。M1 加第二模型（纯攻防 DC）+ 融合 + 2018/2022 回测。
- 纯历史/Elo 模型对西班牙较自信（夺冠 ~22%）、德国偏低（~3%），与 Zeileis 2026 博彩共识
  （西班牙 14.5%）方向一致但更极端，属"纯战绩"口径特征；M1 融合会向共识靠拢。
- **淘汰赛按中立场**（忽略东道主本土加成，世界杯传统视为中立）；小组赛照常加 host。

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

引擎 78 用例（test_structure/annexe_c/normalize/results_store/elo/poisson/dc_fit/tiebreak/simulate/export）；
前端 vitest 7 用例（ProbBar 边界 + format）。

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

- **M0 完成**（2026-06-12）：引擎全链路 + 前端 MVP（仪表盘/小组页/对阵树）+ 首版预测上线。
  揭幕战墨西哥 2-0 南非已回填条件化。
- **M1 待办**：第二模型 + 融合、2018/2022 回测、自动回填 GitHub Actions cron、
  概率演变页 + 模型说明页 + 单场详情页、前端测试补全 + CI。
