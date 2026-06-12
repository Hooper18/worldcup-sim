"""比分矩阵工具的数学性质测试。"""

from __future__ import annotations

import numpy as np
import pytest

from wcsim.models import poisson


def test_pmf_vector_sums_to_one():
    p = poisson.poisson_pmf_vector(1.4, 12)
    assert p.sum() == pytest.approx(1.0)
    assert (p >= 0).all()


def test_score_matrix_normalized():
    mat = poisson.score_matrix(1.5, 1.1)
    assert mat.shape == (13, 13)
    assert mat.sum() == pytest.approx(1.0)
    assert (mat >= 0).all()


def test_outcome_probs_sum_to_one():
    mat = poisson.score_matrix(1.8, 0.9, rho=-0.05)
    ph, pd_, pa = poisson.outcome_probs(mat)
    assert ph + pd_ + pa == pytest.approx(1.0)
    assert ph > pa  # λ 高的一侧胜率高


def test_negative_rho_inflates_low_draws():
    base = poisson.score_matrix(1.3, 1.3, rho=0.0)
    dc = poisson.score_matrix(1.3, 1.3, rho=-0.08)
    assert dc[0, 0] > base[0, 0]
    assert dc[1, 1] > base[1, 1]
    assert dc[1, 0] < base[1, 0]
    assert dc[0, 1] < base[0, 1]
    # 平局总概率上升
    assert np.trace(dc) > np.trace(base)


def test_top_scores_sorted_desc():
    mat = poisson.score_matrix(1.2, 0.8)
    top = poisson.top_scores(mat, 5)
    assert len(top) == 5
    probs = [p for _, _, p in top]
    assert probs == sorted(probs, reverse=True)
    assert top[0][2] == mat.max()


def test_sample_scores_distribution():
    mat = poisson.score_matrix(2.0, 0.5)
    rng = np.random.default_rng(42)
    h, a = poisson.sample_scores(mat, 200_000, rng)
    # 经验频率应接近矩阵概率（蒙特卡洛误差 3 个标准差内）
    emp_00 = float(np.mean((h == 0) & (a == 0)))
    se = (mat[0, 0] * (1 - mat[0, 0]) / 200_000) ** 0.5
    assert abs(emp_00 - mat[0, 0]) < 4 * se
    assert h.mean() == pytest.approx(2.0, abs=0.03)
    assert a.mean() == pytest.approx(0.5, abs=0.02)
