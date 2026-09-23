"""存档：落盘/读回/清档。"""
from __future__ import annotations

from mario.data import save as saved


def test_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(saved, "SAVE_PATH", str(tmp_path / "s.json"))
    saved.save({"done": ["1-1", "1-2"], "stars": {"1-1": {"0": True, "2": True}}})
    back = saved.load()
    assert back["done"] == ["1-1", "1-2"]
    assert back["stars"]["1-1"] == {"0": True, "2": True}


def test_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(saved, "SAVE_PATH", str(tmp_path / "nope.json"))
    assert saved.load() == {"done": [], "stars": {}}


def test_corrupt_file_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    monkeypatch.setattr(saved, "SAVE_PATH", str(p))
    assert saved.load() == {"done": [], "stars": {}}


def test_clear(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    monkeypatch.setattr(saved, "SAVE_PATH", str(p))
    saved.save({"done": ["x"], "stars": {}})
    assert p.exists()
    saved.clear()
    assert not p.exists()


def test_starcoin_collect_persists(app, level, tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(saved, "SAVE_PATH", str(tmp_path / "s.json"))
    from mario.game.objects import StarCoin

    level.spawn(StarCoin, level.player.body.x, level.player.body.y - 10, idx=0)
    for _ in range(4):
        level.update()
        level.input.advance()
    assert saved.load()["stars"]["1-1"]["0"] is True
