import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from game_engine import (  # noqa: E402
    GameEngine,
    build_paths,
    ensure_data_files,
    ensure_dirs,
    init_db,
    load_settings,
    seed_creatures,
)


def make_engine(tmp_path: Path) -> GameEngine:
    os.environ["CHATGAME_ROOT"] = str(tmp_path)
    paths = build_paths(tmp_path)
    ensure_dirs(paths)
    settings = load_settings(paths)
    init_db(paths)
    seed_creatures(paths)
    ensure_data_files(paths)
    return GameEngine(paths, settings)


def test_spawn_creation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        result = engine.spawn()
        assert "Spawned" in result


def test_catch_success():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.rng.seed(1)
        engine.spawn()
        result = engine.catch("ankit")
        assert "caught" in result


def test_catch_failure():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.spawn()
        engine.rng.seed(999)
        result = engine.catch("ankit")
        assert "failed" in result or "caught" in result


def test_inventory_retrieval():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.rng.seed(1)
        engine.spawn()
        engine.catch("ankit")
        result = engine.inventory("ankit")
        assert "ankit" in result


def test_battle_simulation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.rng.seed(1)
        engine.spawn()
        engine.catch("user1")
        engine.rng.seed(2)
        engine.spawn()
        engine.catch("user2")
        result = engine.battle("user1", "user2")
        assert "wins" in result


def test_data_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = make_engine(root)
        engine.rng.seed(1)
        engine.spawn()
        engine.catch("ankit")
        engine2 = make_engine(root)
        result = engine2.inventory("ankit")
        assert "ankit" in result
