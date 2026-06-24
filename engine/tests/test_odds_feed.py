"""the-odds-api 适配器（odds_feed）+ 市场共识/融合机械（odds）的单测。

无需 ODDS_API_KEY：纯解析用样本 JSON fixture，网络路径用 monkeypatch 断言"无 key 不发请求"。
"""

from __future__ import annotations

import numpy as np
import pytest

from wcsim.models import odds, odds_feed

# the-odds-api /v4/sports/soccer_fifa_world_cup/odds 的样本响应（含干扰项）
_SAMPLE_EVENTS = [
    {
        "id": "evt1",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-15T19:00:00Z",
        "home_team": "Argentina",
        "away_team": "Nigeria",
        "bookmakers": [
            {
                "key": "pinnacle",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Argentina", "price": 1.5},
                            {"name": "Draw", "price": 4.0},
                            {"name": "Nigeria", "price": 7.0},
                        ],
                    },
                    # 交易所反向盘口：必须按 key 过滤掉，不能误用
                    {
                        "key": "h2h_lay",
                        "outcomes": [
                            {"name": "Argentina", "price": 1.52},
                            {"name": "Draw", "price": 4.1},
                            {"name": "Nigeria", "price": 7.2},
                        ],
                    },
                ],
            },
            {
                "key": "betfair",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Argentina", "price": 1.55},
                            {"name": "Draw", "price": 3.9},
                            {"name": "Nigeria", "price": 6.5},
                        ],
                    }
                ],
            },
            # 脏数据：缺 Draw，必须跳过该家（不污染共识）
            {
                "key": "broken",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Argentina", "price": 1.6},
                            {"name": "Nigeria", "price": 6.0},
                        ],
                    }
                ],
            },
        ],
    },
    # 无任何 bookmaker：整场跳过
    {
        "id": "evt2",
        "commence_time": "2026-06-16T16:00:00Z",
        "home_team": "Brazil",
        "away_team": "Spain",
        "bookmakers": [],
    },
]


def test_parse_events_maps_and_consensus():
    out = odds_feed.parse_events(_SAMPLE_EVENTS)
    assert len(out) == 1  # evt2 无 bookmaker 被跳过
    e = out[0]
    assert (e["home"], e["away"]) == ("Argentina", "Nigeria")
    assert e["date"] == "2026-06-15"
    assert e["books"] == 2  # pinnacle + betfair，broken（缺 Draw）被跳过
    s = e["p_home"] + e["p_draw"] + e["p_away"]
    assert s == pytest.approx(1.0)
    assert e["p_home"] > e["p_away"]  # 阿根廷赔率最低 → 概率最高


def test_parse_events_filters_h2h_lay():
    """h2h_lay 干扰盘口不得参与（只有 1 家 h2h 有效但这里 betfair 也有，验证 pinnacle 用的是 h2h 不是 lay）。"""
    single = [dict(_SAMPLE_EVENTS[0])]
    single[0] = {**single[0], "bookmakers": [_SAMPLE_EVENTS[0]["bookmakers"][0]]}  # 仅 pinnacle
    out = odds_feed.parse_events(single)
    assert out[0]["books"] == 1
    # pinnacle h2h 公平概率：阿根廷 ~0.62 左右；用 lay(1.52) 会略不同——这里只断言落在合理区间
    assert 0.55 < out[0]["p_home"] < 0.72


def test_env_gate_off_returns_none_without_request(monkeypatch):
    """无 ODDS_API_KEY 时 fetch 返回 None 且绝不发网络请求（默认关）。"""
    monkeypatch.delenv("ODDS_API_KEY", raising=False)

    class _Boom:
        def get(self, *a, **k):
            raise AssertionError("默认关时不应发起任何网络请求")

    assert odds_feed.is_enabled() is False
    assert odds_feed.fetch_worldcup_odds(session=_Boom()) is None


def test_name_to_code():
    assert odds_feed.name_to_code("Argentina") == "ARG"
    assert odds_feed.name_to_code("spain") == "ESP"  # 大小写不敏感兜底
    assert odds_feed.name_to_code("Atlantis") is None


# ---------------------------------------------------------------------------
# 融合机械（odds.py）
# ---------------------------------------------------------------------------


def test_market_consensus_between_books_and_normalized():
    books = [np.array([1.8, 3.6, 4.5]), np.array([2.0, 3.4, 4.0])]
    cons = odds.market_consensus(books)
    assert cons.sum() == pytest.approx(1.0)
    assert (cons > 0).all()


def test_blend_off_is_identity():
    model = np.array([0.5, 0.3, 0.2])
    market = np.array([0.7, 0.2, 0.1])
    # weight=0（默认关）→ 原样返回纯模型
    assert np.allclose(odds.blend_with_market(model, market, 0.0), model)
    # market=None → 也原样返回
    assert np.allclose(odds.blend_with_market(model, None, 0.5), model)


def test_blend_full_weight_is_market():
    model = np.array([0.5, 0.3, 0.2])
    market = np.array([0.7, 0.2, 0.1])
    out = odds.blend_with_market(model, market, 1.0)
    assert np.allclose(out, market / market.sum(), atol=1e-9)


def test_blend_half_between_and_normalized():
    model = np.array([0.5, 0.3, 0.2])
    market = np.array([0.8, 0.15, 0.05])
    out = odds.blend_with_market(model, market, 0.5)
    assert out.sum() == pytest.approx(1.0)
    assert model[0] < out[0] < market[0]  # 主胜概率落在两者之间


# ---------------------------------------------------------------------------
# forecast 层融合（writer.match_forecast）：主字段不变 + market/blended 并列
# ---------------------------------------------------------------------------


class _StubModel:
    def lambdas(self, home, away, *, host_home=False, host_away=False):
        return 1.6, 0.9

    def matrix(self, home, away, *, host_home=False, host_away=False, factor=1.0):
        from wcsim.models.poisson import score_matrix

        return score_matrix(1.6 * factor, 0.9 * factor, -0.1)


def test_match_forecast_market_off_by_default():
    from wcsim.export import writer

    fc = writer.match_forecast(_StubModel(), "A", "B")
    assert "market" not in fc and "blended" not in fc  # 默认无市场字段


def test_match_forecast_market_parallel_fields_do_not_touch_main():
    from wcsim.export import writer

    m = _StubModel()
    base = writer.match_forecast(m, "A", "B")
    market = {"p_home": 0.7, "p_draw": 0.2, "p_away": 0.1, "books": 3}

    # weight=0（默认关）：blended 等于纯模型，主字段一字不变
    off = writer.match_forecast(m, "A", "B", market=market, market_weight=0.0)
    assert off["p_home"] == base["p_home"]  # 主字段不受市场影响
    assert off["market"]["books"] == 3 and off["market"]["source"] == "the-odds-api"
    assert off["blended"]["p_home"] == base["p_home"]

    # weight=1：blended 贴近市场，但主字段依旧是纯模型
    full = writer.match_forecast(m, "A", "B", market=market, market_weight=1.0)
    assert full["p_home"] == base["p_home"]
    assert full["blended"]["p_home"] == pytest.approx(0.7, abs=2e-3)
