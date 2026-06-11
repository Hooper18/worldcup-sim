"""Annexe C 495 行第三名落位表的校验测试。"""

from __future__ import annotations

from itertools import combinations

import pytest

from wcsim.tournament.annexe_c import TABLE, allocate
from wcsim.tournament.structure import GROUP_LETTERS, R32_SLOTS, THIRD_SLOT_MATCHES


def test_exactly_495_keys_covering_all_combinations():
    expected = {"".join(c) for c in combinations(GROUP_LETTERS, 8)}
    assert len(TABLE) == 495
    assert set(TABLE) == expected


def test_every_value_is_permutation_of_key():
    for key, val in TABLE.items():
        assert sorted(val) == sorted(key)


def test_every_assignment_within_official_candidates():
    candidates = {mid: set(R32_SLOTS[mid][1][1:]) for mid in THIRD_SLOT_MATCHES}
    for key, val in TABLE.items():
        for i, mid in enumerate(THIRD_SLOT_MATCHES):
            assert val[i] in candidates[mid]


def test_point_values_from_regulations():
    # 实施计划附录 A 的示例行：ABEFHJKL → 1A v 3E, 1B v 3J, 1D v 3B, 1E v 3F,
    # 1G v 3A, 1I v 3H, 1K v 3L, 1L v 3K
    assert allocate("ABEFHJKL") == {
        79: "E", 85: "J", 81: "B", 74: "F", 82: "A", 77: "H", 87: "L", 80: "K",
    }
    # 首行与末行点值
    assert TABLE["ABCDEFGH"] == "HGBCAFDE"
    assert TABLE["EFGHIJKL"] == "EJIFHGLK"
    assert allocate("EFGHIJKL") == {
        79: "E", 85: "J", 81: "I", 74: "F", 82: "H", 77: "G", 87: "L", 80: "K",
    }


def test_allocate_accepts_any_iterable_order():
    assert allocate(["L", "K", "J", "H", "F", "E", "B", "A"]) == allocate("ABEFHJKL")


def test_allocate_rejects_bad_input():
    with pytest.raises(ValueError):
        allocate("ABCDEFG")  # 7 个组
    with pytest.raises(ValueError):
        allocate("ABCDEFGX")  # 非法字母
