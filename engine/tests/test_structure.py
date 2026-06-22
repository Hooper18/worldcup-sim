"""赛制结构数据的完整性测试（structure.py 自身 import 即校验，这里做更细的断言）。"""

from __future__ import annotations

from wcsim.tournament.structure import (
    GROUP_LETTERS,
    GROUPS,
    KO_CHAIN,
    MATCHES,
    R32_SLOTS,
    STAGE_COUNTS,
    TEAMS,
    THIRD_SLOT_MATCHES,
    has_host_advantage,
    venue_country,
)


def test_104_matches_contiguous_ids():
    assert sorted(MATCHES) == list(range(1, 105))


def test_stage_counts():
    counts: dict[str, int] = {}
    for m in MATCHES.values():
        counts[m["stage"]] = counts.get(m["stage"], 0) + 1
    assert counts == STAGE_COUNTS


def test_48_teams_12_groups():
    assert len(TEAMS) == 48
    assert list(GROUPS) == list(GROUP_LETTERS)
    for g in GROUP_LETTERS:
        assert len(GROUPS[g]) == 4
        for code in GROUPS[g]:
            assert TEAMS[code].group == g


def test_hosts():
    hosts = {c for c, t in TEAMS.items() if t.host}
    assert hosts == {"MEX", "CAN", "USA"}
    assert TEAMS["MEX"].group == "A"
    assert TEAMS["CAN"].group == "B"
    assert TEAMS["USA"].group == "D"


def test_opening_match():
    m1 = MATCHES[1]
    assert m1["home"] == "MEX" and m1["away"] == "RSA"
    assert m1["kickoff_utc"] == "2026-06-11T19:00:00Z"
    assert m1["group"] == "A"


def test_final_and_third_place():
    assert MATCHES[104]["stage"] == "final"
    assert MATCHES[104]["kickoff_utc"].startswith("2026-07-19")
    assert MATCHES[104]["home"] == ("W", 101) and MATCHES[104]["away"] == ("W", 102)
    assert MATCHES[103]["stage"] == "third"
    assert MATCHES[103]["home"] == ("L", 101) and MATCHES[103]["away"] == ("L", 102)


def test_each_team_plays_3_group_matches():
    appearances: dict[str, int] = {}
    for m in MATCHES.values():
        if m["stage"] != "group":
            continue
        for code in (m["home"], m["away"]):
            appearances[code] = appearances.get(code, 0) + 1
    assert set(appearances) == set(TEAMS)
    assert all(n == 3 for n in appearances.values())


def test_group_round_robin_complete():
    for g in GROUP_LETTERS:
        pairs = [
            frozenset((m["home"], m["away"]))
            for m in MATCHES.values()
            if m["stage"] == "group" and m["group"] == g
        ]
        assert len(pairs) == 6
        assert len(set(pairs)) == 6  # 无重复对阵
        codes = set(GROUPS[g])
        for p in pairs:
            assert p <= codes


def test_r32_slots_match_regulations():
    # 规程 12.6 的 16 场固定槽位（与 feed、维基三方一致）
    assert R32_SLOTS[73] == ("2A", "2B")
    assert R32_SLOTS[74] == ("1E", "3ABCDF")
    assert R32_SLOTS[77] == ("1I", "3CDFGH")
    assert R32_SLOTS[79] == ("1A", "3CEFHI")
    assert R32_SLOTS[80] == ("1L", "3EHIJK")
    assert R32_SLOTS[81] == ("1D", "3BEFIJ")
    assert R32_SLOTS[82] == ("1G", "3AEHIJ")
    assert R32_SLOTS[85] == ("1B", "3EFGIJ")
    assert R32_SLOTS[87] == ("1K", "3DEIJL")
    assert R32_SLOTS[88] == ("2D", "2G")
    # 每组第一/第二各出现恰一次
    slots = [s for pair in R32_SLOTS.values() for s in pair]
    assert sorted(s for s in slots if s[0] == "1") == [f"1{g}" for g in GROUP_LETTERS]
    assert sorted(s for s in slots if s[0] == "2") == [f"2{g}" for g in GROUP_LETTERS]


def test_third_slot_matches_order():
    # 分配串槽位顺序 = [1A, 1B, 1D, 1E, 1G, 1I, 1K, 1L]
    firsts = [R32_SLOTS[mid][0] for mid in THIRD_SLOT_MATCHES]
    assert firsts == ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]


def test_ko_chain_closure():
    def sources(stage: str):
        return sorted(
            src for m in MATCHES.values() if m["stage"] == stage for src in (m["home"], m["away"])
        )

    assert sources("r16") == [("W", n) for n in range(73, 89)]
    assert sources("qf") == [("W", n) for n in range(89, 97)]
    assert sources("sf") == [("W", n) for n in range(97, 101)]
    # 每场胜者最多被一场后续比赛引用
    winner_refs = [src for srcs in KO_CHAIN.values() for src in srcs if src[0] == "W"]
    assert len(winner_refs) == len(set(winner_refs))


def test_host_advantage():
    # 三个东道主只在本国境内享主场加成
    assert venue_country("Mexico City Stadium") == "MEX"
    assert venue_country("Toronto Stadium") == "CAN"
    assert venue_country("BC Place Vancouver") == "CAN"
    assert venue_country("Atlanta Stadium") == "USA"
    assert has_host_advantage("MEX", "Mexico City Stadium") is True
    assert has_host_advantage("MEX", "Atlanta Stadium") is False  # 墨西哥客场美国
    assert has_host_advantage("USA", "Seattle Stadium") is True
    assert has_host_advantage("CAN", "BC Place Vancouver") is True
    assert has_host_advantage("BRA", "Mexico City Stadium") is False  # 非东道主无加成


def test_stage_windows_do_not_overlap():
    def kickoffs(stage: str):
        return sorted(m["kickoff_utc"] for m in MATCHES.values() if m["stage"] == stage)

    prev_last = ""
    for stage in ("group", "r32", "r16", "qf", "sf"):
        ks = kickoffs(stage)
        assert prev_last < ks[0]
        prev_last = ks[-1]
