"""Annexe C 查表：晋级的 8 个第三名组别集合 → 各"组第一 vs 第三名"场次的归属。

FIFA 在规程 Annexe C 为全部 C(12,8)=495 种晋级组合各预先固定了唯一分配方案，
小组赛结束即自动锁定，无第二次抽签；落位只取决于组别集合，与第三名 1-8 名次无关。
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

from .annexe_c_data import RAW
from .structure import GROUP_LETTERS, R32_SLOTS, THIRD_SLOT_MATCHES


def _parse() -> dict[str, str]:
    table: dict[str, str] = {}
    for entry in RAW.split():
        key, val = entry.split(":")
        table[key] = val
    return table


# key：晋级第三名的组别集合（8 字母升序串）；value：分配串，
# 第 i 个字母 = THIRD_SLOT_MATCHES[i] 场次的第三名所属组
TABLE: dict[str, str] = _parse()


def allocate(qualified_groups: Iterable[str]) -> dict[int, str]:
    """给定晋级的 8 个第三名所属组，返回 {match_id: 该场第三名所属组}。"""
    key = "".join(sorted(qualified_groups))
    if len(key) != 8 or key not in TABLE:
        raise ValueError(f"非法的第三名组合: {key!r}")
    val = TABLE[key]
    return {THIRD_SLOT_MATCHES[i]: val[i] for i in range(8)}


def _validate() -> None:
    expected_keys = {"".join(c) for c in combinations(GROUP_LETTERS, 8)}
    assert set(TABLE) == expected_keys and len(TABLE) == 495

    # 每个槽位的官方候选组（取自 R32_SLOTS 的 "3XXXXX" 记号）
    candidates = {mid: set(R32_SLOTS[mid][1][1:]) for mid in THIRD_SLOT_MATCHES}
    for key, val in TABLE.items():
        assert sorted(val) == sorted(key), f"{key} 分配串非其排列"
        for i, mid in enumerate(THIRD_SLOT_MATCHES):
            assert val[i] in candidates[mid], f"{key}: 槽位 M{mid} 落位 {val[i]} 超出候选组"


_validate()
