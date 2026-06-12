"""最佳第三名排序与落位（FIFA 规程 Article 13 后半段 + Annexe C）。

排序标准：总积分 → 总净胜球 → 总进球 → 行为分 → FIFA 排名（逐期追溯，这里以
tiebreak_key 代理）。取前 8 晋级，其落位由 Annexe C 查表决定（只取决于晋级第三名的
组别集合，与第三名 1-8 名次本身无关）。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import annexe_c
from .tiebreak import Standing, overall_sort_key


@dataclass
class ThirdPlace:
    group: str
    code: str
    standing: Standing


def rank_third_places(
    thirds: dict[str, Standing],
    *,
    conduct: dict[str, int] | None = None,
    tiebreak_key: dict[str, float] | None = None,
) -> list[ThirdPlace]:
    """对 12 个小组第三名排序，返回从第 1 到第 12 的列表（前 8 晋级）。

    thirds：{组字母: 该组第三名的 Standing}
    """
    conduct = conduct or {}
    tiebreak_key = tiebreak_key or {}
    items = [ThirdPlace(g, st.code, st) for g, st in thirds.items()]
    items.sort(
        key=lambda tp: overall_sort_key(
            tp.standing, conduct.get(tp.code, 0), tiebreak_key.get(tp.code, 0.0)
        )
    )
    return items


def assign_third_slots(
    thirds: dict[str, Standing],
    *,
    conduct: dict[str, int] | None = None,
    tiebreak_key: dict[str, float] | None = None,
) -> dict[int, str]:
    """完整流程：排序 → 取前 8 → Annexe C 查表 → 返回 {match_id: 第三名队伍代码}。

    返回的 8 个 match_id 即 THIRD_SLOT_MATCHES（79, 85, 81, 74, 82, 77, 87, 80）。
    """
    ranked = rank_third_places(thirds, conduct=conduct, tiebreak_key=tiebreak_key)
    qualified = ranked[:8]
    group_to_code = {tp.group: tp.code for tp in qualified}
    slot_to_group = annexe_c.allocate(group_to_code.keys())
    return {mid: group_to_code[g] for mid, g in slot_to_group.items()}
