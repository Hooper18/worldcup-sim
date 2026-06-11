"""全局配置：路径、数据源 URL、模型常量。"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
ENGINE_ROOT = Path(__file__).resolve().parents[2]  # engine/
REPO_ROOT = ENGINE_ROOT.parent
DATA_DIR = ENGINE_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"  # 原始下载缓存（gitignored）
RESULTS_PATH = DATA_DIR / "results.json"  # 真实赛果状态（入库）
PARAMS_PATH = DATA_DIR / "params.json"  # 模型拟合参数（入库）
WEB_DATA_DIR = REPO_ROOT / "web" / "public" / "data"  # 前端 JSON 落点

# ---------------------------------------------------------------------------
# 数据源
# ---------------------------------------------------------------------------
MARTJ42_RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)
MARTJ42_SHOOTOUTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
)
FIXTURE_FEED_URL = "https://fixturedownload.com/feed/json/fifa-world-cup-2026"
ELORATINGS_URL = "https://eloratings.net/World.tsv"

# fixturedownload 网页端对无 UA 的程序请求返回 403，统一带浏览器 UA
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

HTTP_TIMEOUT = 30  # 秒
CACHE_MAX_AGE_HOURS = 6  # 缓存超过该时长则重新下载

# ---------------------------------------------------------------------------
# Elo 常量（eloratings.net 公式）
# ---------------------------------------------------------------------------
ELO_START = 1500.0  # 新队伍初始分
ELO_HOME_ADV = 100.0  # 真主场加成（中立场不加）

# 赛事 K 值：世界杯决赛圈 60 / 洲际决赛圈 50 / 预选赛 40 / 其他 30 / 友谊赛 20
ELO_K_WORLD_CUP = 60.0
ELO_K_CONTINENTAL = 50.0
ELO_K_QUALIFIER = 40.0
ELO_K_OTHER = 30.0
ELO_K_FRIENDLY = 20.0

# ---------------------------------------------------------------------------
# 模型拟合
# ---------------------------------------------------------------------------
FIT_WINDOW_YEARS = 8  # 训练窗口：近 8 年
TIME_DECAY_HALF_LIFE_DAYS = 730  # 时间衰减半衰期（回测网格 {365,540,730,1095} 选优）
MAX_GOALS = 12  # 比分矩阵截断（0..12）

# ---------------------------------------------------------------------------
# 模拟
# ---------------------------------------------------------------------------
N_SIMS_DEFAULT = 100_000
EXTRA_TIME_LAMBDA_FACTOR = 1.0 / 3.0  # 加时 30 分钟 ≈ λ × 1/3
PENALTY_WIN_PROB = 0.5  # 点球大战 50:50（大样本研究支持，无先罚优势）
