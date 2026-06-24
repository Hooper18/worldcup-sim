"""the-odds-api（v4）取数适配器：env `ODDS_API_KEY` 门控、**默认关、不进 cron**。

诚实边界（go/no-go 调研结论，必须如实文档）：
- **没有稳定免费的国家队大赛历史 1X2 赔率源**——the-odds-api 有世界杯历史但仅付费订阅 + 历史端点
  10x credit 倍率（免费 500/月用不起）；football-data.co.uk 只含俱乐部联赛；Kaggle martj42 只有比分。
  故"市场共识该融多少权重"这个参数**无法进 backtest/runner.py 的 LOTO 留一届交叉验证**、无法样本外评估。
- 因此本模块只负责"取当前赔率 → 去 overround → 公平共识概率"；**是否融进 forecast 由调用方 weight 控制
  （默认 0=关）**，且任何"融了更准"的措辞一律禁止（见 [models.odds.blend_with_market]）。
- the-odds-api 是 in-season 模式：世界杯结束 / 回合间隙 sport key 会从活跃列表消失 → 拿不到当前赔率。
- 失败（无 key / 网络 / 休赛期 / 坏数据）一律返回 None/[]，**绝不静默回退陈旧赔率冒充实时**。

取数与展示分离：纯解析 `parse_events`（可用样本 JSON 单测，无需 key）+ 网络 `fetch_worldcup_odds`
（env 门控）。key 只经 requests `params={"apiKey": key}` 传，绝不拼进 URL、绝不进日志。
"""

from __future__ import annotations

import datetime as dt
import os

import numpy as np
import requests

from .. import config
from ..data.normalize import FEED_TO_CODE, MARTJ42_TO_CODE
from . import odds

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
WC_SPORT_KEY = (
    "soccer_fifa_world_cup"  # 世界杯逐场 1X2（has_outrights=false）；运行时仍以 /sports 实测为准
)

# the-odds-api 用通用英文队名，与 martj42 拼写最接近；并表 feed 拼写兜底
_NAME_TO_CODE: dict[str, str] = {**FEED_TO_CODE, **MARTJ42_TO_CODE}


def is_enabled() -> bool:
    """env 门控：仅当显式设置 ODDS_API_KEY 才启用（默认关，ready-but-off）。"""
    return bool(os.environ.get("ODDS_API_KEY"))


def name_to_code(name: str) -> str | None:
    """the-odds-api 英文队名 → 48 队代码；未知返回 None（preview 里跳过、不 raise）。"""
    if name in _NAME_TO_CODE:
        return _NAME_TO_CODE[name]
    low = {k.lower(): v for k, v in _NAME_TO_CODE.items()}
    return low.get(name.lower())


def _date_of(commence_time: str | None) -> str | None:
    if not commence_time:
        return None
    try:
        d = dt.datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        return d.astimezone(dt.UTC).date().isoformat()
    except ValueError:
        return None


def parse_events(events: list[dict], *, method: str = "shin") -> list[dict]:
    """the-odds-api event 数组 → [{date,home,away,p_home,p_draw,p_away,books}]（公平共识概率）。

    按 name 精确匹配 h2h 的 outcomes（不靠数组下标）：home_team→o_home、'Draw'→o_draw、
    away_team→o_away；交易所 h2h_lay 用 key!='h2h' 过滤掉；三项不全的 bookmaker 跳过（防脏数据）。
    每家先去 overround，再跨家 logit 共识。
    """
    out: list[dict] = []
    for ev in events:
        home, away = ev.get("home_team"), ev.get("away_team")
        if not (home and away):
            continue
        books: list[np.ndarray] = []
        for bk in ev.get("bookmakers", []):
            mk = next((m for m in bk.get("markets", []) if m.get("key") == "h2h"), None)
            if not mk:
                continue
            price = {o.get("name"): o.get("price") for o in mk.get("outcomes", [])}
            oh, od, oa = price.get(home), price.get("Draw"), price.get(away)
            if None in (oh, od, oa):
                continue  # 缺任一结局：跳过该家
            books.append(odds.fair_probs(np.array([oh, od, oa], dtype=float), method))
        if not books:
            continue
        cons = odds.consensus(books)
        out.append(
            {
                "date": _date_of(ev.get("commence_time")),
                "home": home,
                "away": away,
                "p_home": float(cons[0]),
                "p_draw": float(cons[1]),
                "p_away": float(cons[2]),
                "books": len(books),
            }
        )
    return out


def _log_quota(resp: requests.Response) -> dict:
    """读响应头记配额（x-requests-remaining/used/last），供逼近上限时停发。"""
    q = {
        "remaining": resp.headers.get("x-requests-remaining"),
        "used": resp.headers.get("x-requests-used"),
        "last": resp.headers.get("x-requests-last"),
    }
    print(f"[odds] 配额 remaining={q['remaining']} used={q['used']} last={q['last']}")
    return q


def sport_active(api_key: str, session: requests.Session) -> bool:
    """GET /v4/sports（不耗配额）确认世界杯 sport key 当前 active（休赛期会消失）。"""
    r = session.get(
        f"{ODDS_API_BASE}/sports", params={"apiKey": api_key}, timeout=config.HTTP_TIMEOUT
    )
    r.raise_for_status()
    return any(s.get("key") == WC_SPORT_KEY and s.get("active") for s in r.json())


def fetch_worldcup_odds(
    *, regions: str = "eu", method: str = "shin", session: requests.Session | None = None
) -> list[dict] | None:
    """拉世界杯当前 1X2 → 公平共识概率列表。

    未启用（无 ODDS_API_KEY）或任何失败 → 返回 None（默认关 / 失败可见、不静默回退）。
    休赛期 sport key 不在活跃列表 → 返回 []（区别于 None：能连但当前无赛事）。
    """
    if not is_enabled():
        return None
    api_key = os.environ["ODDS_API_KEY"]
    session = session or requests.Session()
    try:
        if not sport_active(api_key, session):
            return []  # in-season 模式：休赛期/回合间隙
        r = session.get(
            f"{ODDS_API_BASE}/sports/{WC_SPORT_KEY}/odds",
            params={
                "apiKey": api_key,
                "regions": regions,
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
            timeout=config.HTTP_TIMEOUT,
        )
        _log_quota(r)
        if r.status_code in (401, 422):
            print(f"[odds] the-odds-api {r.status_code}：{r.text[:200]}")
            return None
        r.raise_for_status()
        return parse_events(r.json(), method=method)
    except (requests.RequestException, ValueError) as e:
        # 异常串可能含带 apiKey 查询参数的 URL（requests 的 HTTPError/ConnectionError 会带 url）
        # → 只记异常类型，杜绝 key 经日志泄漏（见模块 docstring 的"绝不进日志"约定）
        print(f"[odds] 拉取失败（{type(e).__name__}），返回 None（不回退陈旧赔率）")
        return None
