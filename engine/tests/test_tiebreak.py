"""小组排名器（2026 头对头 tiebreaker）边界用例。"""

from __future__ import annotations

from wcsim.tournament.tiebreak import compute_standings, rank_group
from wcsim.tournament.third_place import Standing, assign_third_slots, rank_third_places


def codes(standings):
    return [s.code for s in standings]


def test_no_ties_pure_points():
    # A 全胜、B 两胜、C 一胜、D 全负
    matches = [
        ("A", "B", 1, 0), ("A", "C", 2, 0), ("A", "D", 3, 0),
        ("B", "C", 1, 0), ("B", "D", 2, 0),
        ("C", "D", 1, 0),
    ]
    assert codes(rank_group(matches)) == ["A", "B", "C", "D"]


def test_head_to_head_priority_over_goal_difference():
    # 关键用例（2026 新规核心）：A、B 同为 6 分，B 总净胜球(+5)远高于 A(-1)，
    # 但 A 头对头 1-0 胜 B → 头对头优先于净胜球，A 仍第 1。
    matches = [
        ("A", "B", 1, 0),            # 头对头 A 胜 B
        ("A", "C", 1, 0), ("A", "D", 0, 3),  # A 净胜球被 D 拉低
        ("B", "C", 3, 0), ("B", "D", 3, 0),  # B 狂胜攒净胜球
        ("C", "D", 1, 0),
    ]
    r = rank_group(matches)
    assert r[0].pts == r[1].pts == 6
    assert r[0].code == "A"          # 头对头胜者在前
    assert r[1].code == "B"
    assert r[1].gd > r[0].gd         # 尽管 B 总净胜球更高


def test_head_to_head_draw_falls_to_overall_gd():
    # A、B 同分，相互平局 → 看总净胜球，A 净胜更高 → A 第 1
    matches = [
        ("A", "B", 1, 1),            # 头对头平
        ("A", "C", 3, 0), ("A", "D", 2, 0),
        ("B", "C", 1, 0), ("B", "D", 1, 0),
        ("C", "D", 0, 0),
    ]
    # A: 1+3+3=7, B: 1+3+3=7 同分；总 gd A=(0)+3+2=5, B=0+1+1=2 → A 前
    r = rank_group(matches)
    assert codes(r)[:2] == ["A", "B"]
    assert r[0].pts == r[1].pts == 7
    assert r[0].gd > r[1].gd


def test_three_way_circular_tie_falls_to_overall():
    # A>B, B>C, C>A 各 1-0（相互完全并列），三队都赢 D 但比分不同 → 落总净胜球
    matches = [
        ("A", "B", 1, 0), ("B", "C", 1, 0), ("C", "A", 1, 0),
        ("A", "D", 3, 0), ("B", "D", 2, 0), ("C", "D", 1, 0),
    ]
    r = rank_group(matches)
    # A,B,C 各 6 分（相互 1胜1负 + 胜 D），相互 h2h 全平 → 总 gd: A=3, B=2, C=1
    assert [s.code for s in r] == ["A", "B", "C", "D"]
    assert r[0].pts == r[1].pts == r[2].pts == 6


def test_partial_subgroup_recursion():
    # 三队同分，其中两队相互战绩可分、另一队靠总成绩
    # A、B、C 各 6 分。h2h：A 胜 B、B 胜 C、A 胜 C → A 全胜 h2h(第1)，B、C 各 1胜1负
    # 但 B、C 的 h2h（仅 B vs C）B 胜 → B>C
    matches = [
        ("A", "B", 1, 0), ("A", "C", 1, 0), ("B", "C", 1, 0),
        ("A", "D", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0),
    ]
    r = rank_group(matches)
    assert [s.code for s in r] == ["A", "B", "C", "D"]


def test_final_fallback_to_tiebreak_key():
    # A、B 完全对称（相互 0-0，对 C/D 同比分）→ 落 tiebreak_key
    matches = [
        ("A", "B", 0, 0),
        ("A", "C", 1, 0), ("A", "D", 1, 0),
        ("B", "C", 1, 0), ("B", "D", 1, 0),
        ("C", "D", 0, 0),
    ]
    r_a = rank_group(matches, tiebreak_key={"A": 2000.0, "B": 1900.0})
    assert [s.code for s in r_a][:2] == ["A", "B"]
    r_b = rank_group(matches, tiebreak_key={"A": 1800.0, "B": 1900.0})
    assert [s.code for s in r_b][:2] == ["B", "A"]


def test_absolute_determinism_without_keys():
    # 完全对称且无 tiebreak_key → 代码字母序兜底，结果确定
    matches = [
        ("A", "B", 0, 0),
        ("A", "C", 1, 0), ("A", "D", 1, 0),
        ("B", "C", 1, 0), ("B", "D", 1, 0),
        ("C", "D", 0, 0),
    ]
    assert [s.code for s in rank_group(matches)][:2] == ["A", "B"]


def test_conduct_score_breaks_tie():
    # A、B 各方面相同,A 行为分更高（牌更少）→ A 前
    matches = [
        ("A", "B", 0, 0),
        ("A", "C", 1, 0), ("A", "D", 1, 0),
        ("B", "C", 1, 0), ("B", "D", 1, 0),
        ("C", "D", 0, 0),
    ]
    r = rank_group(matches, conduct={"A": 0, "B": -3})
    assert [s.code for s in r][:2] == ["A", "B"]


def test_compute_standings_basic():
    st = compute_standings(["A", "B"], [("A", "B", 2, 1)])
    assert st["A"].pts == 3 and st["A"].gd == 1 and st["A"].gf == 2
    assert st["B"].pts == 0 and st["B"].gd == -1


# ---------------------------------------------------------------------------
# 第三名排序与落位
# ---------------------------------------------------------------------------


def _standing(code, pts, gd, gf):
    return Standing(code=code, played=3, gf=gf, ga=gf - gd, pts=pts)


def test_rank_third_places_orders_by_overall():
    thirds = {
        "A": _standing("a", 4, 1, 3),
        "B": _standing("b", 6, 2, 4),  # 最高分
        "C": _standing("c", 4, 2, 3),  # 同 4 分但净胜球高于 A
    }
    ranked = rank_third_places(thirds)
    assert [tp.code for tp in ranked] == ["b", "c", "a"]


def test_assign_third_slots_maps_via_annexe_c():
    # 构造 8 个明显晋级的组（高分）+ 4 个出局组（0 分）
    thirds = {}
    strong = "ABEFHJKL"  # 对应附录 A 示例 ABEFHJKL:EJBFAHLK
    for g in "ABCDEFGHIJKL":
        pts = 5 if g in strong else 0
        thirds[g] = _standing(f"3{g}", pts, 1 if g in strong else -3, 2)
    slots = assign_third_slots(thirds)
    # 槽位映射应与 Annexe C 示例一致：M79←3E, M85←3J, M81←3B, M74←3F, ...
    assert slots[79] == "3E"
    assert slots[85] == "3J"
    assert slots[81] == "3B"
    assert slots[74] == "3F"
    assert slots[82] == "3A"
    assert slots[77] == "3H"
    assert slots[87] == "3L"
    assert slots[80] == "3K"
    assert set(slots) == {79, 85, 81, 74, 82, 77, 87, 80}
