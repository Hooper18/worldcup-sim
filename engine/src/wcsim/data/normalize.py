"""队名归一：martj42 / fixturedownload 两套拼写 ↔ 队伍代码。

两个数据源对同一队的英文名不一致（martj42 用通用名，feed 用 FIFA 官方名），
全部经实测核对。任何未知队名一律 raise——宁可中断也不要静默错配。
"""

from __future__ import annotations

from ..tournament.structure import TEAMS

# martj42 数据集拼写 → 队伍代码（2026-06 实测）
MARTJ42_TO_CODE: dict[str, str] = {
    "Mexico": "MEX",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Czech Republic": "CZE",
    "Canada": "CAN",
    "Bosnia and Herzegovina": "BIH",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Brazil": "BRA",
    "Morocco": "MAR",
    "Haiti": "HAI",
    "Scotland": "SCO",
    "United States": "USA",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Turkey": "TUR",
    "Germany": "GER",
    "Curaçao": "CUW",
    "Ivory Coast": "CIV",
    "Ecuador": "ECU",
    "Netherlands": "NED",
    "Japan": "JPN",
    "Sweden": "SWE",
    "Tunisia": "TUN",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Iran": "IRN",
    "New Zealand": "NZL",
    "Spain": "ESP",
    "Cape Verde": "CPV",
    "Saudi Arabia": "KSA",
    "Uruguay": "URU",
    "France": "FRA",
    "Senegal": "SEN",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Portugal": "POR",
    "DR Congo": "COD",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
}

# fixturedownload feed 拼写 → 队伍代码（FIFA 官方风格，2026-06 实测）
FEED_TO_CODE: dict[str, str] = {
    "Mexico": "MEX",
    "South Africa": "RSA",
    "Korea Republic": "KOR",
    "Czechia": "CZE",
    "Canada": "CAN",
    "Bosnia and Herzegovina": "BIH",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Brazil": "BRA",
    "Morocco": "MAR",
    "Haiti": "HAI",
    "Scotland": "SCO",
    "USA": "USA",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Türkiye": "TUR",
    "Germany": "GER",
    "Curaçao": "CUW",
    "Côte d'Ivoire": "CIV",
    "Ecuador": "ECU",
    "Netherlands": "NED",
    "Japan": "JPN",
    "Sweden": "SWE",
    "Tunisia": "TUN",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "IR Iran": "IRN",
    "New Zealand": "NZL",
    "Spain": "ESP",
    "Cabo Verde": "CPV",
    "Saudi Arabia": "KSA",
    "Uruguay": "URU",
    "France": "FRA",
    "Senegal": "SEN",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Portugal": "POR",
    "Congo DR": "COD",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
}

CODE_TO_MARTJ42: dict[str, str] = {v: k for k, v in MARTJ42_TO_CODE.items()}


class UnknownTeamError(KeyError):
    """数据源出现无法归一的队名。"""


def martj42_to_code(name: str) -> str:
    try:
        return MARTJ42_TO_CODE[name]
    except KeyError:
        raise UnknownTeamError(f"martj42 队名无法归一: {name!r}") from None


def feed_to_code(name: str) -> str:
    try:
        return FEED_TO_CODE[name]
    except KeyError:
        raise UnknownTeamError(f"fixturedownload 队名无法归一: {name!r}") from None


def code_to_martj42(code: str) -> str:
    """队伍代码 → martj42 拼写（查询历史数据 / Elo 用）。"""
    try:
        return CODE_TO_MARTJ42[code]
    except KeyError:
        raise UnknownTeamError(f"未知队伍代码: {code!r}") from None


def _validate() -> None:
    assert set(MARTJ42_TO_CODE.values()) == set(TEAMS), "martj42 映射未覆盖全部 48 队"
    assert set(FEED_TO_CODE.values()) == set(TEAMS), "feed 映射未覆盖全部 48 队"
    assert len(MARTJ42_TO_CODE) == 48 and len(FEED_TO_CODE) == 48
    # feed 拼写须与 structure 的 name_en 完全一致（teams.json 用 name_en 展示）
    for name, code in FEED_TO_CODE.items():
        assert TEAMS[code].name_en == name, f"{code}: feed {name!r} != structure {TEAMS[code].name_en!r}"


_validate()
