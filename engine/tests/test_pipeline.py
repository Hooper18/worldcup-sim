"""pipeline 编排的纯逻辑测试（不触网络/缓存）。

重点锁 cron 的"诚实"约定：feed 刷新失败必须**响亮**返回 failed=True（供 wcsim update 发
::error:: + 非零退出让 cron 变红），且沿用已有 store、绝不静默吞掉冒充成功。
"""

from __future__ import annotations

from wcsim import pipeline


def test_refresh_results_from_feed_failure_is_loud(monkeypatch):
    def boom(**_kw):
        raise RuntimeError("feed 503")

    monkeypatch.setattr(pipeline.fetch, "load_fixture_feed", boom)
    existing = {1: {"h": 2, "a": 0, "after": "FT"}}
    results, failed, error = pipeline.refresh_results_from_feed(dict(existing), force_fetch=False)

    assert failed is True
    assert error is not None and "feed 503" in error
    assert results == existing  # 沿用已有 store，不丢、不清空


def test_refresh_results_from_feed_merges_and_saves(monkeypatch):
    monkeypatch.setattr(pipeline.fetch, "load_fixture_feed", lambda **_kw: [])
    monkeypatch.setattr(
        pipeline.results_store,
        "parse_feed",
        lambda _feed: {1: {"h": 1, "a": 0, "after": "FT"}},
    )
    saved: dict = {}
    monkeypatch.setattr(
        pipeline.results_store,
        "save_store",
        lambda store: saved.update(called=True, store=dict(store)),
    )

    results, failed, error = pipeline.refresh_results_from_feed({}, force_fetch=False)

    assert failed is False and error is None
    assert results[1] == {"h": 1, "a": 0, "after": "FT"}
    assert saved.get("called") is True  # 有新完赛才写盘


def test_refresh_results_from_feed_warns_on_changed_score(monkeypatch, capsys):
    # feed 与已存比分不一致：按「赛果不可变」保留旧值，但必须响亮告警（不静默）
    existing = {1: {"h": 1, "a": 0, "after": "FT"}}
    monkeypatch.setattr(pipeline.fetch, "load_fixture_feed", lambda **_kw: [])
    monkeypatch.setattr(
        pipeline.results_store, "parse_feed", lambda _feed: {1: {"h": 2, "a": 2, "after": "FT"}}
    )
    monkeypatch.setattr(pipeline.results_store, "save_store", lambda _store: None)

    results, failed, error = pipeline.refresh_results_from_feed(dict(existing), force_fetch=False)

    assert failed is False
    assert results[1] == existing[1]  # 保留旧值（赛果不可变）
    assert "::warning::" in capsys.readouterr().out  # 但响亮告警


def test_refresh_results_from_feed_no_new_skips_save(monkeypatch):
    existing = {1: {"h": 1, "a": 0, "after": "FT"}}
    monkeypatch.setattr(pipeline.fetch, "load_fixture_feed", lambda **_kw: [])
    monkeypatch.setattr(pipeline.results_store, "parse_feed", lambda _feed: dict(existing))
    saved: dict = {}
    monkeypatch.setattr(
        pipeline.results_store, "save_store", lambda store: saved.update(called=True)
    )

    results, failed, error = pipeline.refresh_results_from_feed(dict(existing), force_fetch=False)

    assert failed is False and error is None
    assert results == existing
    assert saved.get("called") is None  # 无新完赛不写盘（cron 据此跳过 commit）
