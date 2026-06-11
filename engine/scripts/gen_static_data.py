"""一次性生成静态数据模块（生成产物入库，本脚本仅为可追溯留档）。

1. data/cache/fixtures.json（fixturedownload feed 快照，2026-06-12 抓取）
   → src/wcsim/tournament/fixtures_data.py
2. 实施计划附录 A 的 Annexe C 495 行表（提取自 FIFA 官方规程 PDF，经程序化校验）
   → src/wcsim/tournament/annexe_c_data.py

用法：
    python scripts/gen_static_data.py <fixtures.json 路径> <计划 markdown 路径>
"""

from __future__ import annotations

import json
import re
import sys
from itertools import combinations
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ENGINE_ROOT / "src" / "wcsim" / "tournament"

# fixturedownload feed 队名 → 队伍代码（FIFA 三字码）。未知队名直接 KeyError。
FEED_NAME_TO_CODE: dict[str, str] = {
    "Algeria": "ALG",
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA",
    "Cabo Verde": "CPV",
    "Canada": "CAN",
    "Colombia": "COL",
    "Congo DR": "COD",
    "Côte d'Ivoire": "CIV",
    "Croatia": "CRO",
    "Curaçao": "CUW",
    "Czechia": "CZE",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Germany": "GER",
    "Ghana": "GHA",
    "Haiti": "HAI",
    "IR Iran": "IRN",
    "Iraq": "IRQ",
    "Japan": "JPN",
    "Jordan": "JOR",
    "Korea Republic": "KOR",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Portugal": "POR",
    "Qatar": "QAT",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "South Africa": "RSA",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "SUI",
    "Tunisia": "TUN",
    "Türkiye": "TUR",
    "Uruguay": "URU",
    "USA": "USA",
    "Uzbekistan": "UZB",
}

STAGE_BY_ROUND = {1: "group", 2: "group", 3: "group", 4: "r32", 5: "r16", 6: "qf", 7: "sf"}

SLOT_RE = re.compile(r"^(?:[12][A-L]|3[A-L]{5})$")


def gen_fixtures(fixtures_path: Path) -> None:
    rows = json.loads(fixtures_path.read_text(encoding="utf-8"))
    assert len(rows) == 104, f"feed 应有 104 场，实际 {len(rows)}"
    rows.sort(key=lambda r: r["MatchNumber"])

    lines: list[str] = []
    for r in rows:
        mid = r["MatchNumber"]
        rnd = r["RoundNumber"]
        if rnd == 8:
            stage = "third" if mid == 103 else "final"
        else:
            stage = STAGE_BY_ROUND[rnd]

        kickoff = r["DateUtc"].replace(" ", "T")
        assert re.match(r"^2026-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", kickoff), kickoff

        if stage == "group":
            group = r["Group"].removeprefix("Group ")
            assert group in "ABCDEFGHIJKL", group
            home = FEED_NAME_TO_CODE[r["HomeTeam"]]
            away = FEED_NAME_TO_CODE[r["AwayTeam"]]
            home_repr, away_repr = repr(home), repr(away)
            group_repr = repr(group)
        else:
            group_repr = "None"
            if stage == "r32":
                # R32 槽位 feed 给定（如 "2A" / "1E" / "3ABCDF"），原样保留
                assert SLOT_RE.match(r["HomeTeam"]), r["HomeTeam"]
                assert SLOT_RE.match(r["AwayTeam"]), r["AwayTeam"]
                home_repr, away_repr = repr(r["HomeTeam"]), repr(r["AwayTeam"])
            else:
                # R16 起 feed 为 TBD，槽位由 structure.KO_CHAIN（FIFA 规程 12.7-12.11）补全
                assert r["HomeTeam"] == "To be announced", r["HomeTeam"]
                home_repr = away_repr = "None"

        lines.append(
            f'    {{"id": {mid}, "stage": "{stage}", "group": {group_repr}, '
            f'"kickoff_utc": "{kickoff}", "venue": {repr(r["Location"])}, '
            f'"home": {home_repr}, "away": {away_repr}}},'
        )

    out = OUT_DIR / "fixtures_data.py"
    out.write_text(
        '"""104 场赛程静态数据。由 scripts/gen_static_data.py 自 fixturedownload feed 生成，勿手改。\n'
        "\n"
        "feed 快照时间：2026-06-12（开幕战开球前）。group 阶段 home/away 为队伍代码；\n"
        'r32 为 feed 槽位记号（"1A"/"2A"/"3ABCDF"）；r16 起为 None（由 structure.KO_CHAIN 补全）。\n'
        '"""\n\nFIXTURES: list[dict] = [\n' + "\n".join(lines) + "\n]\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"fixtures_data.py: {len(rows)} matches written")


def gen_annexe_c(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    pairs = re.findall(r"\b([A-L]{8}):([A-L]{8})\b", text)
    table: dict[str, str] = {}
    for key, val in pairs:
        if key in table:
            assert table[key] == val, f"同 key 不同值：{key} -> {table[key]} / {val}"
        else:
            table[key] = val

    assert len(table) == 495, f"应恰 495 个组合，实际 {len(table)}"
    expected = {"".join(c) for c in combinations("ABCDEFGHIJKL", 8)}
    assert set(table) == expected, "key 集合不等于全部 C(12,8) 组合"
    for key, val in table.items():
        assert sorted(val) == sorted(key), f"{key} 的分配串不是其排列：{val}"

    entries = [f"{k}:{table[k]}" for k in sorted(table)]
    body_lines = [" ".join(entries[i : i + 5]) for i in range(0, len(entries), 5)]

    out = OUT_DIR / "annexe_c_data.py"
    out.write_text(
        '"""FIFA 世界杯 2026 规程 Annexe C：8 个最佳第三 → 槽位的 495 行官方映射表。\n'
        "\n"
        "由 scripts/gen_static_data.py 自实施计划附录 A 生成（原始提取自 FIFA 官方规程 PDF，\n"
        "经多源核验 + 程序化校验：495 key = 全部 C(12,8)、分配串为 key 的排列、落位均在官方候选组）。\n"
        "勿手改。格式：`晋级第三名组别集合(升序):分配串`，分配串 8 字母依次对应槽位\n"
        "[1A, 1B, 1D, 1E, 1G, 1I, 1K, 1L]（即场次 M79, M85, M81, M74, M82, M77, M87, M80）。\n"
        '"""\n\nRAW = """\\\n' + "\n".join(body_lines) + '\n"""\n',
        encoding="utf-8",
        newline="\n",
    )
    print(f"annexe_c_data.py: {len(table)} entries written")


def main() -> None:
    fixtures_path = Path(sys.argv[1])
    plan_path = Path(sys.argv[2])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gen_fixtures(fixtures_path)
    gen_annexe_c(plan_path)


if __name__ == "__main__":
    main()
