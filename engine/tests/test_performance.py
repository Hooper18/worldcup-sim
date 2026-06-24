"""本届实战表现：赛前预测重建匹配 + 打分聚合。"""

from __future__ import annotations

import pandas as pd

from wcsim.backtest import performance
from wcsim.data.normalize import code_to_martj42
from wcsim.models.bundle import ModelBundle
from wcsim.models.dc_attack import DcAttackParams
from wcsim.models.dc_elo import DcEloParams
from wcsim.tournament.simulate import CODES

MEX, RSA = code_to_martj42("MEX"), code_to_martj42("RSA")


def test_find_pre_match_elo_window_edge():
    # 回归:kickoff 次日 02:00Z、martj42 行在前一日午夜 —— 归一化到日期 ±1 天必须命中
    # （旧版用 UTC 时刻 -1 天会把它刷掉）
    wc = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-11"),
                "home_team": MEX,
                "away_team": RSA,
                "home_elo_pre": 1800.0,
                "away_elo_pre": 1600.0,
            }
        ]
    )
    got = performance._find_pre_match_elo(wc, "MEX", "RSA", pd.Timestamp("2026-06-12T02:00:00"))
    assert got == (1800.0, 1600.0)


def test_find_pre_match_elo_orientation_and_miss():
    # martj42 行主客相反 → 按 MATCHES 朝向交换返回
    wc = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-11"),
                "home_team": RSA,
                "away_team": MEX,
                "home_elo_pre": 1600.0,
                "away_elo_pre": 1800.0,
            }
        ]
    )
    assert performance._find_pre_match_elo(
        wc, "MEX", "RSA", pd.Timestamp("2026-06-11T19:00:00")
    ) == (1800.0, 1600.0)
    # 窗口外 → None
    assert performance._find_pre_match_elo(wc, "MEX", "RSA", pd.Timestamp("2026-06-20")) is None


def _synthetic_bundle():
    att = DcAttackParams(
        mu=0.1,
        home_adv=0.25,
        rho=-0.04,
        att={c: 0.5 - 0.02 * i for i, c in enumerate(CODES)},
        def_={c: -0.5 + 0.02 * i for i, c in enumerate(CODES)},
        half_life_days=730,
        n_matches=7000,
        cutoff="2026-06-11",
        teams=CODES,
    )
    elo_p = DcEloParams(
        beta0=0.10,
        beta1=0.73,
        gamma=0.23,
        rho=-0.043,
        half_life_days=730,
        n_matches=7768,
        cutoff="2026-06-11",
    )
    return ModelBundle(dc_elo=elo_p, dc_attack=att, weight_dc_elo=0.5, half_life_days=730)


def _synthetic_df():
    rows = []
    # 赛前历史(<cutoff):墨西哥连胜→Elo 高，南非连败→Elo 低
    for i in range(4):
        rows.append((f"2025-09-0{i + 1}", MEX, "Brazil", 2, 0, "Friendly"))
        rows.append((f"2025-10-0{i + 1}", "Spain", RSA, 3, 0, "Friendly"))
    # M1 揭幕战(2026 WC):墨西哥 3-0 南非
    rows.append(("2026-06-11", MEX, RSA, 3, 0, "FIFA World Cup"))
    return (
        pd.DataFrame(
            [
                {
                    "date": pd.Timestamp(d),
                    "home_team": h,
                    "away_team": a,
                    "home_score": hs,
                    "away_score": a_,
                    "tournament": t,
                    "neutral": False,
                }
                for (d, h, a, hs, a_, t) in rows
            ]
        )
        .sort_values("date")
        .reset_index(drop=True)
    )


def test_compute_performance_scores_knockout():
    # 淘汰赛：参赛队码取自 store（parse_feed 记 home/away），中立场，group 为 None
    df = _synthetic_df()
    extra = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-28"),  # M73 r32 kickoff 当日
                "home_team": MEX,
                "away_team": RSA,
                "home_score": 2,
                "away_score": 1,
                "tournament": "FIFA World Cup",
                "neutral": True,
            }
        ]
    )
    df = pd.concat([df, extra]).sort_values("date").reset_index(drop=True)
    out = performance.compute_performance(
        df=df,
        bundle=_synthetic_bundle(),
        results={73: {"h": 2, "a": 1, "after": "FT", "home": "MEX", "away": "RSA"}},
    )
    pm = next(p for p in out["per_match"] if p["id"] == 73)
    assert pm["home"] == "MEX" and pm["away"] == "RSA"
    assert pm["group"] is None  # 淘汰赛无小组
    assert pm["actual"] == {"h": 2, "a": 1, "outcome": "home"}
    assert out["n_scored"] >= 1


def test_compute_performance_shape_and_scoring():
    out = performance.compute_performance(
        df=_synthetic_df(),
        bundle=_synthetic_bundle(),
        results={1: {"h": 3, "a": 0, "after": "FT"}},
    )
    assert out["n_scored"] == 1 and out["n_skipped"] == 0
    pm = out["per_match"][0]
    assert pm["id"] == 1 and pm["home"] == "MEX" and pm["away"] == "RSA"
    assert pm["actual"] == {"h": 3, "a": 0, "outcome": "home"}
    assert set(pm["pred"]) == {"p_home", "p_draw", "p_away", "pick", "top_score"}
    # 墨西哥赛前 Elo 远高 + 主场 → 预测主胜，实际 3-0 主胜 → 命中
    assert pm["pred"]["pick"] == "home"
    assert pm["hit"] is True
    assert 0.0 <= pm["rps"] <= 1.0
    # 汇总三方对比 + 累计走势
    for arm in ("fused", "elo_baseline", "climatology"):
        assert set(out[arm]) == {"rps", "brier", "log_loss", "hit_rate"}
    assert len(out["cumulative"]) == 1 and out["cumulative"][0]["n"] == 1
