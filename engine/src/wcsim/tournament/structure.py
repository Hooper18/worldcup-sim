"""2026 世界杯赛制结构：48 队、12 组、104 场、淘汰赛串联与槽位规则。

数据来源（均经多源交叉核验，详见仓库 README 与实施计划）：
- 分组与小组赛赛程：fixturedownload feed（与 Wikipedia 12 组页、ESPN、NBC 三方一致）
- R32 槽位与候选组：FIFA 规程 12.6（与 feed、英文维基 knockout stage 页一致）
- 淘汰赛串联：FIFA 规程 12.7-12.11
"""

from __future__ import annotations

from dataclasses import dataclass

from .fixtures_data import FIXTURES

GROUP_LETTERS = "ABCDEFGHIJKL"

STAGE_ORDER = ("group", "r32", "r16", "qf", "sf", "third", "final")

# 各阶段场次数（小组赛 72 + 淘汰赛 32 = 104）
STAGE_COUNTS = {"group": 72, "r32": 16, "r16": 8, "qf": 4, "sf": 2, "third": 1, "final": 1}


@dataclass(frozen=True)
class Team:
    code: str
    name_en: str  # FIFA 风格英文名（与 fixturedownload feed 一致）
    name_zh: str
    flag: str
    group: str
    host: bool = False


_TEAM_ROWS: list[tuple[str, str, str, str, str, bool]] = [
    # code, name_en, name_zh, flag, group, host
    ("MEX", "Mexico", "墨西哥", "🇲🇽", "A", True),
    ("RSA", "South Africa", "南非", "🇿🇦", "A", False),
    ("KOR", "Korea Republic", "韩国", "🇰🇷", "A", False),
    ("CZE", "Czechia", "捷克", "🇨🇿", "A", False),
    ("CAN", "Canada", "加拿大", "🇨🇦", "B", True),
    ("BIH", "Bosnia and Herzegovina", "波黑", "🇧🇦", "B", False),
    ("QAT", "Qatar", "卡塔尔", "🇶🇦", "B", False),
    ("SUI", "Switzerland", "瑞士", "🇨🇭", "B", False),
    ("BRA", "Brazil", "巴西", "🇧🇷", "C", False),
    ("MAR", "Morocco", "摩洛哥", "🇲🇦", "C", False),
    ("HAI", "Haiti", "海地", "🇭🇹", "C", False),
    ("SCO", "Scotland", "苏格兰", "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "C", False),
    ("USA", "USA", "美国", "🇺🇸", "D", True),
    ("PAR", "Paraguay", "巴拉圭", "🇵🇾", "D", False),
    ("AUS", "Australia", "澳大利亚", "🇦🇺", "D", False),
    ("TUR", "Türkiye", "土耳其", "🇹🇷", "D", False),
    ("GER", "Germany", "德国", "🇩🇪", "E", False),
    ("CUW", "Curaçao", "库拉索", "🇨🇼", "E", False),
    ("CIV", "Côte d'Ivoire", "科特迪瓦", "🇨🇮", "E", False),
    ("ECU", "Ecuador", "厄瓜多尔", "🇪🇨", "E", False),
    ("NED", "Netherlands", "荷兰", "🇳🇱", "F", False),
    ("JPN", "Japan", "日本", "🇯🇵", "F", False),
    ("SWE", "Sweden", "瑞典", "🇸🇪", "F", False),
    ("TUN", "Tunisia", "突尼斯", "🇹🇳", "F", False),
    ("BEL", "Belgium", "比利时", "🇧🇪", "G", False),
    ("EGY", "Egypt", "埃及", "🇪🇬", "G", False),
    ("IRN", "IR Iran", "伊朗", "🇮🇷", "G", False),
    ("NZL", "New Zealand", "新西兰", "🇳🇿", "G", False),
    ("ESP", "Spain", "西班牙", "🇪🇸", "H", False),
    ("CPV", "Cabo Verde", "佛得角", "🇨🇻", "H", False),
    ("KSA", "Saudi Arabia", "沙特阿拉伯", "🇸🇦", "H", False),
    ("URU", "Uruguay", "乌拉圭", "🇺🇾", "H", False),
    ("FRA", "France", "法国", "🇫🇷", "I", False),
    ("SEN", "Senegal", "塞内加尔", "🇸🇳", "I", False),
    ("IRQ", "Iraq", "伊拉克", "🇮🇶", "I", False),
    ("NOR", "Norway", "挪威", "🇳🇴", "I", False),
    ("ARG", "Argentina", "阿根廷", "🇦🇷", "J", False),
    ("ALG", "Algeria", "阿尔及利亚", "🇩🇿", "J", False),
    ("AUT", "Austria", "奥地利", "🇦🇹", "J", False),
    ("JOR", "Jordan", "约旦", "🇯🇴", "J", False),
    ("POR", "Portugal", "葡萄牙", "🇵🇹", "K", False),
    ("COD", "Congo DR", "刚果（金）", "🇨🇩", "K", False),
    ("UZB", "Uzbekistan", "乌兹别克斯坦", "🇺🇿", "K", False),
    ("COL", "Colombia", "哥伦比亚", "🇨🇴", "K", False),
    ("ENG", "England", "英格兰", "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "L", False),
    ("CRO", "Croatia", "克罗地亚", "🇭🇷", "L", False),
    ("GHA", "Ghana", "加纳", "🇬🇭", "L", False),
    ("PAN", "Panama", "巴拿马", "🇵🇦", "L", False),
]

TEAMS: dict[str, Team] = {
    code: Team(code, en, zh, flag, group, host) for code, en, zh, flag, group, host in _TEAM_ROWS
}

# 各组队伍（种子顺位排列，仅用于展示；排名一律由比赛结果计算）
GROUPS: dict[str, list[str]] = {
    g: [t.code for t in TEAMS.values() if t.group == g] for g in GROUP_LETTERS
}

# ---------------------------------------------------------------------------
# R32 槽位（FIFA 规程 12.6）。槽位记号：
#   "1A"=A 组第一，"2A"=A 组第二，"3ABCDF"=最佳第三（官方候选组 {A,B,C,D,F}）
# ---------------------------------------------------------------------------
R32_SLOTS: dict[int, tuple[str, str]] = {
    73: ("2A", "2B"),
    74: ("1E", "3ABCDF"),
    75: ("1F", "2C"),
    76: ("1C", "2F"),
    77: ("1I", "3CDFGH"),
    78: ("2E", "2I"),
    79: ("1A", "3CEFHI"),
    80: ("1L", "3EHIJK"),
    81: ("1D", "3BEFIJ"),
    82: ("1G", "3AEHIJ"),
    83: ("2K", "2L"),
    84: ("1H", "2J"),
    85: ("1B", "3EFGIJ"),
    86: ("1J", "2H"),
    87: ("1K", "3DEIJL"),
    88: ("2D", "2G"),
}

# Annexe C 分配串的槽位顺序：第 i 个字母分给哪场"组第一 vs 第三名"
# 依次对应 1A, 1B, 1D, 1E, 1G, 1I, 1K, 1L
THIRD_SLOT_MATCHES: tuple[int, ...] = (79, 85, 81, 74, 82, 77, 87, 80)

# ---------------------------------------------------------------------------
# 淘汰赛串联（FIFA 规程 12.7-12.11）。来源记号：("W", 73)=第 73 场胜者，("L", 101)=负者
# ---------------------------------------------------------------------------
Source = tuple[str, int]

KO_CHAIN: dict[int, tuple[Source, Source]] = {
    89: (("W", 74), ("W", 77)),
    90: (("W", 73), ("W", 75)),
    91: (("W", 76), ("W", 78)),
    92: (("W", 79), ("W", 80)),
    93: (("W", 83), ("W", 84)),
    94: (("W", 81), ("W", 82)),
    95: (("W", 86), ("W", 88)),
    96: (("W", 85), ("W", 87)),
    97: (("W", 89), ("W", 90)),
    98: (("W", 93), ("W", 94)),
    99: (("W", 91), ("W", 92)),
    100: (("W", 95), ("W", 96)),
    101: (("W", 97), ("W", 98)),
    102: (("W", 99), ("W", 100)),
    103: (("L", 101), ("L", 102)),
    104: (("W", 101), ("W", 102)),
}

# ---------------------------------------------------------------------------
# 场馆 → 所在国（主办国在本国境内比赛才有主场加成；martj42 的 neutral 标记同口径）
# ---------------------------------------------------------------------------
_MEX_VENUES = {"Mexico City Stadium", "Guadalajara Stadium", "Monterrey Stadium"}
_CAN_VENUES = {"Toronto Stadium", "BC Place Vancouver"}


def venue_country(venue: str) -> str:
    """场馆所在国的队伍代码（"MEX" / "CAN" / "USA"）。"""
    if venue in _MEX_VENUES:
        return "MEX"
    if venue in _CAN_VENUES:
        return "CAN"
    return "USA"


def has_host_advantage(team_code: str, venue: str) -> bool:
    """该队在该场馆是否享有东道主主场加成。"""
    return TEAMS[team_code].host and venue_country(venue) == team_code


# ---------------------------------------------------------------------------
# 组装 104 场完整结构：MATCHES[id] = {id, stage, group, kickoff_utc, venue, home, away}
#   group  阶段：home/away 为队伍代码
#   r32    阶段：home/away 为槽位记号（与 R32_SLOTS 一致）
#   r16 起：home/away 为来源记号 ("W", n) / ("L", n)
# ---------------------------------------------------------------------------


def _build_matches() -> dict[int, dict]:
    matches: dict[int, dict] = {}
    for row in FIXTURES:
        m = dict(row)
        mid, stage = m["id"], m["stage"]
        if stage == "r32":
            expected = R32_SLOTS[mid]
            if (m["home"], m["away"]) != expected:
                raise AssertionError(
                    f"M{mid} feed 槽位 {m['home']}/{m['away']} 与规程 {expected} 不符"
                )
        elif stage not in ("group", "r32"):
            m["home"], m["away"] = KO_CHAIN[mid]
        matches[mid] = m
    return matches


MATCHES: dict[int, dict] = _build_matches()


def _validate() -> None:
    assert len(TEAMS) == 48 and len({t.code for t in TEAMS.values()}) == 48
    assert all(len(GROUPS[g]) == 4 for g in GROUP_LETTERS)
    assert [TEAMS[c].group for g in GROUP_LETTERS for c in GROUPS[g]] == [
        g for g in GROUP_LETTERS for _ in range(4)
    ]
    assert {c for c, t in TEAMS.items() if t.host} == {"MEX", "CAN", "USA"}

    assert sorted(MATCHES) == list(range(1, 105))
    counts: dict[str, int] = {}
    for m in MATCHES.values():
        counts[m["stage"]] = counts.get(m["stage"], 0) + 1
    assert counts == STAGE_COUNTS, counts

    # 每组 6 场恰为 4 队两两对阵
    for g in GROUP_LETTERS:
        pairs = {
            frozenset((m["home"], m["away"]))
            for m in MATCHES.values()
            if m["stage"] == "group" and m["group"] == g
        }
        codes = GROUPS[g]
        expected_pairs = {frozenset((a, b)) for i, a in enumerate(codes) for b in codes[i + 1 :]}
        assert pairs == expected_pairs, f"组 {g} 对阵不完整"

    # 串联封闭性：r32 的 16 个胜者恰好各被 r16 引用一次，依此类推
    def _sources(stage: str) -> list[Source]:
        return [
            src for m in MATCHES.values() if m["stage"] == stage for src in (m["home"], m["away"])
        ]

    assert sorted(_sources("r16")) == [("W", n) for n in range(73, 89)]
    assert sorted(_sources("qf")) == [("W", n) for n in range(89, 97)]
    assert sorted(_sources("sf")) == [("W", n) for n in range(97, 101)]
    assert sorted(_sources("third")) == [("L", 101), ("L", 102)]
    assert sorted(_sources("final")) == [("W", 101), ("W", 102)]

    # 槽位完备性：每组的第一、第二各出现一次；第三名槽位恰 8 个
    slots = [s for pair in R32_SLOTS.values() for s in pair]
    assert sorted(s for s in slots if s.startswith("1")) == [f"1{g}" for g in GROUP_LETTERS]
    assert sorted(s for s in slots if s.startswith("2")) == [f"2{g}" for g in GROUP_LETTERS]
    thirds = [s for s in slots if s.startswith("3")]
    assert len(thirds) == 8
    assert [MATCHES[mid]["away"] for mid in THIRD_SLOT_MATCHES] == [
        R32_SLOTS[mid][1] for mid in THIRD_SLOT_MATCHES
    ]

    # 阶段时间窗顺序：上一阶段最晚开球早于下一阶段最早开球
    def _kickoffs(stage: str) -> list[str]:
        return sorted(m["kickoff_utc"] for m in MATCHES.values() if m["stage"] == stage)

    prev_last = ""
    for stage in ("group", "r32", "r16", "qf", "sf"):
        ks = _kickoffs(stage)
        assert prev_last < ks[0], f"{stage} 与上一阶段时间窗重叠"
        prev_last = ks[-1]
    assert _kickoffs("third")[0] < _kickoffs("final")[0]


_validate()
