"""小组排名器（FIFA 规程 Article 13，2026 新规：头对头优先）。

排名标准依次：
  Step 1（仅看并列球队相互间比赛）：① 相互积分 ② 相互净胜球 ③ 相互进球
      —— 若分出部分球队后仍有更小子集并列，对该子集重新应用 ①-③（递归）
  Step 2（对 Step 1 无法区分的子集，且不重启）：④ 总净胜球 ⑤ 总进球 ⑥ 行为分
  Step 3：⑦ FIFA 排名（这里以一个外部 tiebreak_key 传入，模拟中用赛前 Elo 代理）

行为分（黄牌等）在模拟中不可得，conduct 默认全 0；最终绝对兜底用队代码字母序，
保证排名完全确定。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

Match = tuple[str, str, int, int]  # (home, away, home_goals, away_goals)


@dataclass
class Standing:
    code: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    pts: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga


def compute_standings(teams: list[str], matches: list[Match]) -> dict[str, Standing]:
    """统计 teams 在给定比赛中的积分榜（只计 home/away 都属于 teams 的场次）。"""
    st = {t: Standing(t) for t in teams}
    tset = set(teams)
    for home, away, hg, ag in matches:
        if home not in tset or away not in tset:
            continue
        sh, sa = st[home], st[away]
        sh.played += 1
        sa.played += 1
        sh.gf += hg
        sh.ga += ag
        sa.gf += ag
        sa.ga += hg
        if hg > ag:
            sh.won += 1
            sa.lost += 1
            sh.pts += 3
        elif hg < ag:
            sa.won += 1
            sh.lost += 1
            sa.pts += 3
        else:
            sh.drawn += 1
            sa.drawn += 1
            sh.pts += 1
            sa.pts += 1
    return st


def rank_group(
    matches: list[Match],
    *,
    conduct: dict[str, int] | None = None,
    tiebreak_key: dict[str, float] | None = None,
) -> list[Standing]:
    """对一个小组的全部比赛排名，返回从第 1 到第 4 的 Standing 列表。"""
    teams = sorted({t for m in matches for t in (m[0], m[1])})
    conduct = conduct or {}
    tiebreak_key = tiebreak_key or {}
    full = compute_standings(teams, matches)
    ordered = _order(teams, matches, full, conduct, tiebreak_key)
    return [full[c] for c in ordered]


def _order(
    teams: list[str],
    all_matches: list[Match],
    full: dict[str, Standing],
    conduct: dict[str, int],
    tk: dict[str, float],
) -> list[str]:
    by_pts: dict[int, list[str]] = defaultdict(list)
    for t in teams:
        by_pts[full[t].pts].append(t)
    out: list[str] = []
    for pts in sorted(by_pts, reverse=True):
        out.extend(_resolve(by_pts[pts], all_matches, full, conduct, tk))
    return out


def _resolve(
    tied: list[str],
    all_matches: list[Match],
    full: dict[str, Standing],
    conduct: dict[str, int],
    tk: dict[str, float],
) -> list[str]:
    """对积分相同的一组球队排序。"""
    if len(tied) == 1:
        return list(tied)

    # Step 1：相互间战绩
    h2h = compute_standings(tied, all_matches)
    subgroups: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    for t in tied:
        s = h2h[t]
        subgroups[(s.pts, s.gd, s.gf)].append(t)

    if len(subgroups) == 1:
        # 相互间完全无法区分 → Step 2/3：总成绩兜底
        return _overall_order(tied, full, conduct, tk)

    out: list[str] = []
    for key in sorted(subgroups, reverse=True):
        sub = subgroups[key]
        if len(sub) == 1:
            out.extend(sub)
        else:
            # 子集严格变小（len(subgroups) > 1 保证），递归重算相互战绩
            out.extend(_resolve(sub, all_matches, full, conduct, tk))
    return out


def _overall_order(
    tied: list[str],
    full: dict[str, Standing],
    conduct: dict[str, int],
    tk: dict[str, float],
) -> list[str]:
    """Step 2/3：总净胜球 → 总进球 → 行为分 → tiebreak_key → 代码字母序（绝对兜底）。

    用"越小越靠前"的升序 key（对越大越好的指标取负），最后 code 升序保证确定性。
    """
    return sorted(
        tied,
        key=lambda t: (
            -full[t].gd,
            -full[t].gf,
            -conduct.get(t, 0),
            -tk.get(t, 0.0),
            t,
        ),
    )


def overall_sort_key(
    standing: Standing, conduct: int, tk: float
) -> tuple[float, float, float, float, float, str]:
    """供第三名跨组排序复用的总成绩 key（升序，越小越靠前）。

    顺序：总积分 → 总净胜球 → 总进球 → 行为分 → FIFA 排名代理 → 代码字母序。
    """
    return (
        -standing.pts,
        -standing.gd,
        -standing.gf,
        -conduct,
        -float(tk),
        standing.code,
    )
