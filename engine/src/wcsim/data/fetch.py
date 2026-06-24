"""数据抓取：martj42 历史赛果、fixturedownload feed。

全部带本地缓存（CACHE_DIR），默认 6 小时内不重复下载；写入采用临时文件 + 原子替换，
避免下载中断留下半截文件。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

from .. import config


def _download(url: str, dest: Path, *, headers: dict[str, str] | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)
    return dest


def _is_fresh(path: Path, max_age_hours: float) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < max_age_hours * 3600


def fetch_results_csv(*, force: bool = False) -> Path:
    """martj42 results.csv（1872 至今全部国际 A 级赛，含 2026 世界杯赛程行）。"""
    dest = config.CACHE_DIR / "results.csv"
    if force or not _is_fresh(dest, config.CACHE_MAX_AGE_HOURS):
        _download(config.MARTJ42_RESULTS_URL, dest)
    return dest


def fetch_shootouts_csv(*, force: bool = False) -> Path:
    """martj42 shootouts.csv（点球大战胜者）。"""
    dest = config.CACHE_DIR / "shootouts.csv"
    if force or not _is_fresh(dest, config.CACHE_MAX_AGE_HOURS):
        _download(config.MARTJ42_SHOOTOUTS_URL, dest)
    return dest


def fetch_fixture_feed(*, force: bool = False) -> Path:
    """fixturedownload JSON feed（104 场赛程 + 赛后回填比分）。需带浏览器 UA。"""
    dest = config.CACHE_DIR / "fixtures.json"
    if force or not _is_fresh(dest, config.CACHE_MAX_AGE_HOURS):
        _download(config.FIXTURE_FEED_URL, dest, headers={"User-Agent": config.BROWSER_UA})
    return dest


# ---------------------------------------------------------------------------
# 加载
# ---------------------------------------------------------------------------


def load_results(*, force: bool = False) -> pd.DataFrame:
    """加载 martj42 全量赛果，date 解析为 Timestamp，并过滤掉未来排程行（无比分）。

    返回列：date, home_team, away_team, home_score, away_score, tournament,
    city, country, neutral。只保留已完赛（比分非空）的行。
    """
    path = fetch_results_csv(force=force)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    played = df.dropna(subset=["home_score", "away_score"]).copy()
    played["home_score"] = played["home_score"].astype(int)
    played["away_score"] = played["away_score"].astype(int)
    played["neutral"] = played["neutral"].astype(bool)
    return played.sort_values("date").reset_index(drop=True)


def load_shootouts(*, force: bool = False) -> pd.DataFrame:
    path = fetch_shootouts_csv(force=force)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_fixture_feed(*, force: bool = False) -> list[dict]:
    path = fetch_fixture_feed(force=force)
    return json.loads(path.read_text(encoding="utf-8"))
