"""真实赛果状态：engine/data/results.json 的读写与"新完赛场次"检测。

results.json 结构（match_id 为字符串 key，JSON 限制）：
{
  "1": {"h": 2, "a": 1, "after": "FT"},
  "77": {"h": 1, "a": 1, "after": "PEN", "pen_winner": "home"}
}
- h/a：常规时间或加时后的最终比分（点球大战的进球不计入）
- after："FT"（90 分钟）| "AET"（加时）| "PEN"（点球决胜）
- pen_winner：仅 after=="PEN" 时存在，"home" | "away"

数据来源以 fixturedownload feed 为主（feed 对加时/点球的具体表示需在 32 强首日实测，
解析失败的场次会被跳过并告警，绝不写入可疑数据）；martj42 为回退源。
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .. import config
from ..tournament.structure import MATCHES
from .normalize import feed_to_code, martj42_to_code

Result = dict[str, Any]


def load_store() -> dict[int, Result]:
    if not config.RESULTS_PATH.exists():
        return {}
    raw = json.loads(config.RESULTS_PATH.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def save_store(store: dict[int, Result]) -> None:
    config.RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(k): store[k] for k in sorted(store)}
    config.RESULTS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


# ---------------------------------------------------------------------------
# feed 解析
# ---------------------------------------------------------------------------


def parse_feed(feed: list[dict]) -> dict[int, Result]:
    """从 feed 提取已完赛场次。比分为空的场次跳过；解析异常的场次跳过并告警。"""
    out: dict[int, Result] = {}
    for row in feed:
        mid = row["MatchNumber"]
        hs, as_ = row.get("HomeTeamScore"), row.get("AwayTeamScore")
        if hs is None or as_ is None:
            continue
        if mid not in MATCHES:
            print(f"[results] 警告：feed 出现未知场次号 {mid}，跳过")
            continue

        m = MATCHES[mid]
        if m["stage"] == "group":
            # 小组赛：队名严格核对，对不上立即中止（说明 feed 或映射有问题）
            home, away = feed_to_code(row["HomeTeam"]), feed_to_code(row["AwayTeam"])
            if (home, away) != (m["home"], m["away"]):
                raise ValueError(
                    f"M{mid} feed 对阵 {home}/{away} 与赛程 {m['home']}/{m['away']} 不符"
                )

        result: Result = {"h": int(hs), "a": int(as_), "after": "FT"}

        if m["stage"] != "group" and int(hs) == int(as_):
            # 淘汰赛平比分 ⇒ 点球决胜。feed 的 Winner 字段给出胜者队名。
            winner = (row.get("Winner") or "").strip()
            if not winner:
                print(f"[results] 警告：M{mid} 淘汰赛平比分但无 Winner，跳过待下轮抓取")
                continue
            try:
                winner_code = feed_to_code(winner)
            except Exception:
                print(f"[results] 警告：M{mid} Winner {winner!r} 无法归一，跳过")
                continue
            result["after"] = "PEN"
            result["pen_winner"] = _pen_side(mid, winner_code, row)
            if result["pen_winner"] is None:
                print(f"[results] 警告：M{mid} 无法判定点球胜方，跳过")
                continue

        out[mid] = result
    return out


def _pen_side(mid: int, winner_code: str, row: dict) -> str | None:
    """根据 Winner 队名判断点球胜方是 home 还是 away。"""
    try:
        home = feed_to_code(row["HomeTeam"])
        away = feed_to_code(row["AwayTeam"])
    except Exception:
        return None
    if winner_code == home:
        return "home"
    if winner_code == away:
        return "away"
    return None


# ---------------------------------------------------------------------------
# martj42 回退解析（按队伍对 + 日期 ±1 天匹配；martj42 记当地日期，feed 为 UTC）
# ---------------------------------------------------------------------------


def parse_martj42(results_df: pd.DataFrame, resolved: dict[int, tuple[str, str]]) -> dict[int, Result]:
    """从 martj42 已完赛行提取 2026 世界杯赛果。

    resolved：{match_id: (home_code, away_code)}——淘汰赛场次需调用方先解析出实际对阵；
    小组赛场次可直接由 MATCHES 提供。martj42 主表记录 120 分钟比分，点球胜者在
    shootouts.csv（此处不解析点球，标记 after="FT"/"AET" 不可区分时一律按平局处理，
    淘汰赛平局场次需 shootouts 数据补全后才入库——由调用方处理）。
    """
    wc = results_df[results_df["tournament"] == "FIFA World Cup"]
    wc = wc[wc["date"] >= "2026-06-01"]
    out: dict[int, Result] = {}
    for mid, (home, away) in resolved.items():
        m = MATCHES[mid]
        kickoff = pd.Timestamp(m["kickoff_utc"].replace("Z", ""))
        window = wc[
            (wc["date"] >= kickoff - pd.Timedelta(days=1))
            & (wc["date"] <= kickoff + pd.Timedelta(days=1))
        ]
        hit = window[
            (window["home_team"].map(_safe_code) == home)
            & (window["away_team"].map(_safe_code) == away)
        ]
        if len(hit) == 1:
            r = hit.iloc[0]
            res: Result = {"h": int(r["home_score"]), "a": int(r["away_score"]), "after": "FT"}
            if m["stage"] != "group" and res["h"] == res["a"]:
                # 平比分淘汰赛需要点球胜者，martj42 主表给不了 ⇒ 跳过，等 shootouts/feed
                continue
            out[mid] = res
        elif len(hit) > 1:
            print(f"[results] 警告：martj42 中 M{mid} 匹配到多行，跳过")
    return out


def _safe_code(name: str) -> str | None:
    try:
        return martj42_to_code(name)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def new_finished(old: dict[int, Result], new: dict[int, Result]) -> list[int]:
    """返回 new 中新增的已完赛场次号（已存在的场次不重复返回，赛果不可变）。"""
    return sorted(mid for mid in new if mid not in old)
