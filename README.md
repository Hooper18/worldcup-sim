# worldcup-sim — 2026 世界杯比分预测与全赛程模拟

基于各队历史战绩(1872 年以来全部国际 A 级赛)预测 2026 美加墨世界杯每场比分,
蒙特卡洛模拟整届 104 场赛事直到产生冠军;世界杯期间自动回填真实赛果、条件重模拟,
追踪各队夺冠概率随赛事推进的演变。

## 结构

- `engine/` — Python 3.12 + uv。数据管道(martj42 历史赛果)→ 自算 Elo →
  Dixon-Coles 比分模型 → 蒙特卡洛 1e5 次整届模拟 → 导出 JSON 到 `web/public/data/`
- `web/` — React 18 + TypeScript + Vite + Tailwind。纯静态展示(Vercel 部署),
  读 `public/data/*.json`

## 常用命令

```bash
# 引擎(在 engine/ 下)
uv sync                       # 安装依赖
uv run wcsim fetch            # 拉取历史数据
uv run wcsim fit              # 拟合模型
uv run wcsim simulate         # 蒙特卡洛模拟
uv run wcsim export           # 导出前端 JSON
uv run wcsim update           # 一条龙:抓赛果→有新完赛才重模拟→导出
uv run pytest                 # 测试

# 前端(在 web/ 下)
npm install
npm run dev
npm run test
npm run build
```

## 数据源

- 历史比赛:[martj42/international_results](https://github.com/martj42/international_results)(CC0,每日更新)
- 赛程/赛果:[fixturedownload.com](https://fixturedownload.com/results/fifa-world-cup-2026)
- Elo 由 martj42 历史全量重放自算(无外部 Elo 数据源)
