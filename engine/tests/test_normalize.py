"""队名归一映射的覆盖与严格性测试。"""

from __future__ import annotations

import pytest

from wcsim.data.normalize import (
    FEED_TO_CODE,
    MARTJ42_TO_CODE,
    UnknownTeamError,
    code_to_martj42,
    feed_to_code,
    martj42_to_code,
)
from wcsim.tournament.structure import TEAMS


def test_both_sources_cover_all_48_teams():
    assert set(MARTJ42_TO_CODE.values()) == set(TEAMS)
    assert set(FEED_TO_CODE.values()) == set(TEAMS)
    assert len(MARTJ42_TO_CODE) == 48
    assert len(FEED_TO_CODE) == 48


def test_round_trip_martj42():
    for name, code in MARTJ42_TO_CODE.items():
        assert martj42_to_code(name) == code
        assert code_to_martj42(code) == name


def test_known_spelling_divergences():
    # 两源对同一队的不同拼写都要能归一到同一代码
    assert martj42_to_code("South Korea") == feed_to_code("Korea Republic") == "KOR"
    assert martj42_to_code("Turkey") == feed_to_code("Türkiye") == "TUR"
    assert martj42_to_code("Czech Republic") == feed_to_code("Czechia") == "CZE"
    assert martj42_to_code("DR Congo") == feed_to_code("Congo DR") == "COD"
    assert martj42_to_code("Cape Verde") == feed_to_code("Cabo Verde") == "CPV"
    assert martj42_to_code("Ivory Coast") == feed_to_code("Côte d'Ivoire") == "CIV"
    assert martj42_to_code("United States") == feed_to_code("USA") == "USA"
    assert martj42_to_code("Iran") == feed_to_code("IR Iran") == "IRN"


def test_unknown_name_raises():
    with pytest.raises(UnknownTeamError):
        martj42_to_code("Atlantis")
    with pytest.raises(UnknownTeamError):
        feed_to_code("Korea DPR")  # 朝鲜未晋级，出现即报错
    with pytest.raises(UnknownTeamError):
        code_to_martj42("XXX")


def test_feed_names_match_structure_name_en():
    for name, code in FEED_TO_CODE.items():
        assert TEAMS[code].name_en == name
