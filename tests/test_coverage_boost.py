import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from game_engine import (
    GameEngine,
    BattlePokemon,
    build_paths,
    compute_derived_hp,
    compute_derived_special_atk,
    compute_derived_special_def,
    compute_derived_stats,
    creature_emoji,
    db_session,
    ensure_data_files,
    ensure_dirs,
    find_root,
    init_db,
    load_settings,
    normalize_username,
    now_ts,
    seed_creatures,
    setup_logging,
    _try_parse_streamerbot_setting,
    _get_streamerbot_overrides,
    _get_discord_webhook_override,
)
from type_chart import format_type_weaknesses, get_type_multiplier, get_type_weaknesses


def close_loggers():
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    cmd = logging.getLogger("cmd")
    for h in list(cmd.handlers):
        h.close()
        cmd.removeHandler(h)


def make_engine(tmp_path: Path) -> GameEngine:
    os.environ["CHATGAME_ROOT"] = str(tmp_path)
    paths = build_paths(tmp_path)
    ensure_dirs(paths)
    settings = load_settings(paths)
    settings["discord_inventory_webhook_url"] = ""
    init_db(paths)
    seed_creatures(paths)
    ensure_data_files(paths)
    return GameEngine(paths, settings)


def test_type_chart_empty_attack():
    assert get_type_multiplier("", ["Water"]) == 1.0
    assert get_type_multiplier(None, ["Water"]) == 1.0
    assert get_type_multiplier("water", ["fire"]) == 2.0
    assert get_type_multiplier("  FIRE  ", ["grass"]) == 2.0

    # Test get_type_weaknesses
    assert get_type_weaknesses([]) == []
    assert get_type_weaknesses(None) == []
    pikachu_weak = get_type_weaknesses(["Electric"])
    assert pikachu_weak == [("Ground", 2.0)]

    charizard_weak = get_type_weaknesses(["Fire", "Flying"])
    assert ("Rock", 4.0) in charizard_weak
    assert ("Water", 2.0) in charizard_weak
    assert ("Electric", 2.0) in charizard_weak
    # Verify 4x comes first
    assert charizard_weak[0] == ("Rock", 4.0)

    # Test format_type_weaknesses
    assert format_type_weaknesses([]) == "None"
    assert format_type_weaknesses(["Electric"]) == "Ground (2x)"
    assert format_type_weaknesses(["Fire", "Flying"]) == "Rock (4x), Electric (2x), Water (2x)"


def test_creature_emojis_and_traits():
    assert creature_emoji("Pikachu") == "⚡"
    assert creature_emoji("Bulbasaur") == "🌿"
    assert creature_emoji("Charmander") == "🔥"
    assert creature_emoji("Squirtle") == "💧"
    assert creature_emoji("Rattata") == "⭐"

    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        settings = engine.settings
        # Derived stats for Brave, Tank, Swift
        atk, df, spd = compute_derived_stats(100, 100, 100, 10, 5, 5, 5, "Brave", settings)
        assert atk > 100
        atk_tank, df_tank, spd_tank = compute_derived_stats(100, 100, 100, 10, 5, 5, 5, "Tank", settings)
        assert df_tank > 100
        atk_swift, df_swift, spd_swift = compute_derived_stats(100, 100, 100, 10, 5, 5, 5, "Swift", settings)
        assert spd_swift > 100

        sp_atk_brave = compute_derived_special_atk(100, 10, 5, "Brave", settings)
        assert sp_atk_brave > 100
        sp_def_tank = compute_derived_special_def(100, 10, 5, "Tank", settings)
        assert sp_def_tank > 100
        close_loggers()


def test_settings_streamerbot_overrides():
    assert _try_parse_streamerbot_setting("spawn_interval_seconds", "10") == 10
    assert _try_parse_streamerbot_setting("spawn_interval_seconds", "invalid") is None
    assert _try_parse_streamerbot_setting("unknown_setting", "10") is None

    os.environ["STREAMERBOT_SPAWN_INTERVAL_SECONDS"] = "15"
    overrides = _get_streamerbot_overrides()
    assert overrides.get("spawn_interval_seconds") == 15
    os.environ.pop("STREAMERBOT_SPAWN_INTERVAL_SECONDS", None)

    os.environ["DISCORD_INVENTORY_WEBHOOK_URL"] = "http://example.com/webhook"
    discord_override = _get_discord_webhook_override()
    assert discord_override["discord_inventory_webhook_url"] == "http://example.com/webhook"
    os.environ.pop("DISCORD_INVENTORY_WEBHOOK_URL", None)


def test_find_root_and_logging():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        os.environ["CHATGAME_ROOT"] = str(tmp_path)
        root = find_root()
        assert root == tmp_path.resolve()

        paths = build_paths(tmp_path)
        setup_logging(paths)
        assert paths.log_file.parent.exists()
        close_loggers()


def test_pokedex_and_stats_commands():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Test empty pokedex
        assert "Invalid username" in engine.pokedex("")
        assert "has no creatures yet" in engine.pokedex("nonexistent_user")

        # Test stats edge cases
        assert "Invalid username" in engine.stats("", "P1")
        assert "has no creatures" in engine.stats("nonexistent_user", "P1")

        # Catch a pokemon for user
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "testuser")
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Pikachu'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'testuser', ?, 5, 20, ?, 1, 0, 1000)
                """,
                (u_id, c_id, int(time.time()))
            )
            conn.execute("INSERT INTO pokedex (user_id, creature_id) VALUES (?, ?)", (u_id, c_id))

        pokedex_res = engine.pokedex("testuser")
        assert "Pikachu" in pokedex_res

        stats_by_pid = engine.stats("testuser", "P1")
        assert "Pikachu" in stats_by_pid
        assert "Type:** Electric" in stats_by_pid
        assert "Weakness:** Ground (2x)" in stats_by_pid

        stats_by_name = engine.stats("testuser", "Pikachu")
        assert "Pikachu" in stats_by_name
        assert "Type:** Electric" in stats_by_name
        assert "Weakness:** Ground (2x)" in stats_by_name

        stats_by_number = engine.stats("testuser", "25")
        assert "Pikachu" in stats_by_number
        assert "Type:** Electric" in stats_by_number
        assert "Weakness:** Ground (2x)" in stats_by_number

        # Add dual-type Pokemon to verify dual typing and multiple weaknesses
        with db_session(engine.paths) as conn:
            bulba_id = conn.execute("SELECT id FROM creatures WHERE name = 'Bulbasaur'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P2', ?, 'testuser', ?, 5, 0, ?, 0, 0, 1000)
                """,
                (u_id, bulba_id, int(time.time())),
            )
        stats_dual = engine.stats("testuser", "Bulbasaur")
        assert "Type:** Grass / Poison" in stats_dual
        assert "Weakness:** Fire (2x), Flying (2x), Ice (2x), Psychic (2x)" in stats_dual

        # Test unowned Pokemon by name and number
        stats_unowned_name = engine.stats("testuser", "Mewtwo")
        assert "Type:** Psychic" in stats_unowned_name
        assert "Weakness:** Bug (2x), Dark (2x), Ghost (2x)" in stats_unowned_name
        assert "you don't have this Pokémon in your collection" in stats_unowned_name

        stats_unowned_num = engine.stats("testuser", "#150")
        assert "Type:** Psychic" in stats_unowned_num
        assert "Weakness:** Bug (2x), Dark (2x), Ghost (2x)" in stats_unowned_num
        assert "you don't have this Pokémon in your collection" in stats_unowned_num

        # Test brand new user querying unowned Pokemon
        stats_new_user = engine.stats("brand_new_user", "Charizard")
        assert "Type:** Fire / Flying" in stats_new_user
        assert "Rock (4x)" in stats_new_user
        assert "you don't have this Pokémon in your collection" in stats_new_user

        stats_invalid = engine.stats("testuser", "NonexistentPokemon")
        assert "has no NonexistentPokemon in their inventory" in stats_invalid
        close_loggers()


def test_bag_and_use_commands():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        assert "Invalid username" in engine.bag("")
        assert "your Bag is empty" in engine.bag("emptyuser")

        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "baguser")
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'fire-stone', 2)", (u_id,))

        bag_res = engine.bag("baguser")
        assert "fire-stone" in bag_res

        # Test use command error cases
        assert "Invalid username" in engine.use("", "fire-stone", "P1")
        assert "you do not have a water-stone" in engine.use("baguser", "water-stone", "P1")
        assert "do not own a Pokémon with PID P999" in engine.use("baguser", "fire-stone", "P999")
        close_loggers()


def test_catch_edge_cases():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        assert "Invalid username" in engine.catch("")
        assert "No active spawn" in engine.catch("user1")

        # Active spawn and catch fail / cooldown
        engine.spawn()
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "user1")
            # Set catch cooldown
            conn.execute("UPDATE users SET last_catch_at = ? WHERE id = ?", (now_ts(), u_id))
        
        assert "cooldown active" in engine.catch("user1")

        # Test specialty ball without item in bag
        with db_session(engine.paths) as conn:
            conn.execute("UPDATE users SET last_catch_at = 0 WHERE id = ?", (u_id,))
        assert "do not have any great ball" in engine.catch("user1", "great")
        assert "do not have any ultra ball" in engine.catch("user1", "ultra")

        # Test full inventory
        engine.settings["max_inventory_size"] = 1
        with db_session(engine.paths) as conn:
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Pikachu'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'user1', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (u_id, c_id, int(time.time()))
            )
        assert "Inventory full" in engine.catch("user1")
        close_loggers()


def test_battle_and_accept_validation_errors():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Battle validations
        assert "Invalid battle participants" in engine.battle("", "user2", "P1")
        assert "Invalid battle participants" in engine.battle("user1", "user1", "P1")

        with db_session(engine.paths) as conn:
            u1_id = engine._ensure_user(conn, "user1")
            u2_id = engine._ensure_user(conn, "user2")
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Pikachu'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'user1', ?, 5, 0, ?, 0, 0, 1000)
                """,
                (u1_id, c_id, int(time.time()))
            )

        assert "has no creatures to battle" in engine.battle("user1", "user2", "P1")

        # Add creature for user2
        with db_session(engine.paths) as conn:
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P2', ?, 'user2', ?, 5, 0, ?, 0, 0, 1000)
                """,
                (u2_id, c_id, int(time.time()))
            )

        challenge = engine.battle("user1", "user2", "P1")
        assert "challenged" in challenge

        # Accept validations
        assert "Invalid accept participants" in engine.accept("", "user1", "P2")
        assert "Invalid accept participants" in engine.accept("user2", "user2", "P2")
        assert "No pending challenge" in engine.accept("user2", "nonexistent", "P2")
        close_loggers()


def test_trade_and_accepttrade_validation_errors():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Trade validations
        assert "Invalid trade participants" in engine.trade("", "user2", "P1")
        assert "Invalid trade participants" in engine.trade("user1", "user1", "P1")

        with db_session(engine.paths) as conn:
            u1_id = engine._ensure_user(conn, "user1")
            u2_id = engine._ensure_user(conn, "user2")
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Pikachu'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'user1', ?, 5, 0, ?, 0, 0, 1000)
                """,
                (u1_id, c_id, int(time.time()))
            )

        trade_res = engine.trade("user1", "user2", "P1")
        assert "wants to trade" in trade_res

        # Accepttrade validations
        assert "Invalid trade participants" in engine.accepttrade("", "user1", "P2")
        assert "Invalid trade participants" in engine.accepttrade("user2", "user2", "P2")
        assert "No pending trade offer" in engine.accepttrade("user2", "nonexistent", "P2")
        close_loggers()


def test_leaderboard_command():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Empty leaderboard
        empty_lb = engine.leaderboard()
        assert "Top Players by ELO" in empty_lb

        # Add users with ELO
        with db_session(engine.paths) as conn:
            u1_id = engine._ensure_user(conn, "topuser")
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Charizard'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'topuser', ?, 20, 0, ?, 10, 0, 1250)
                """,
                (u1_id, c_id, int(time.time()))
            )

        lb = engine.leaderboard()
        assert "topuser" in lb
        close_loggers()


def test_item_targets_helper():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        targets_fire = engine._get_item_targets("fire-stone")
        assert "Eevee" in targets_fire
        targets_metal = engine._get_item_targets("metal-coat")
        assert "Onix" in targets_metal
        close_loggers()


def test_simulate_battle_branches():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Special attack pokemon (e.g. Alakazam / Gengar) vs Physical (Aerodactyl)
        p1 = BattlePokemon(
            inv_id="P1", owner="u1", name="Alakazam", level=10, xp=0, trait="Berserk",
            elo=1000, wins=0, losses=0, hp_iv=15, atk_iv=15, def_iv=15, spd_iv=15,
            base_hp=55, base_attack=50, base_defense=45, base_speed=120, base_sp_atk=135, base_sp_def=95,
            types=["Psychic"], creature_id=65
        )
        p2 = BattlePokemon(
            inv_id="P2", owner="u2", name="Gengar", level=10, xp=0, trait="Swift",
            elo=1000, wins=0, losses=0, hp_iv=10, atk_iv=10, def_iv=10, spd_iv=10,
            base_hp=60, base_attack=65, base_defense=60, base_speed=110, base_sp_atk=130, base_sp_def=75,
            types=["Ghost", "Poison"], creature_id=94
        )

        engine.rng.seed(42)
        transcript, log, winner = engine._simulate_battle(p1, p2)
        assert len(transcript) > 0
        assert winner in ["u1", "u2"]
        close_loggers()


def test_resolver_helpers():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "u1")
            c1_id = conn.execute("SELECT id FROM creatures WHERE name = 'Bulbasaur'").fetchone()[0]
            c2_id = conn.execute("SELECT id FROM creatures WHERE name = 'Ivysaur'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'u1', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (u_id, c1_id, int(time.time()))
            )
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P2', ?, 'u1', ?, 10, 0, ?, 0, 0, 1000)
                """,
                (u_id, c2_id, int(time.time()))
            )

            res1 = engine._resolve_inventory_pokemon(conn, u_id, "1")
            assert res1[0] == "P1"

            res_pid = engine._resolve_inventory_pokemon(conn, u_id, "P2")
            assert res_pid[0] == "P2"

            res_name = engine._resolve_inventory_pokemon(conn, u_id, "Ivysaur")
            assert res_name[0] == "P2"

            res_trade = engine._resolve_trade_pokemon(conn, u_id, "u1", "P1")
            assert res_trade[0] == "P1"
        close_loggers()


def test_overlay_test_methods(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda x: None)
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        assert "Test battle triggered" in engine.test_battle()
        assert "evolved into" in engine.test_evolution("user1", "Eevee", "Flareon")
        assert "Test trade triggered" in engine.test_trade("user1", "user2", "Onix", "Steelix")
        close_loggers()


def test_item_targets_all_items():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        items = [
            "moon-stone", "water-stone", "thunder-stone", "fire-stone", "leaf-stone",
            "sun-stone", "black-augurite", "oval-stone", "electirizer", "magmarizer",
            "metal-coat", "kings-rock", "up-grade", "dubious-disc", "protector", "dragon-scale"
        ]
        for item in items:
            targets = engine._get_item_targets(item)
            assert isinstance(targets, list)
        close_loggers()


def test_stone_evolutions_via_use():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "evouser")
            eevee_id = conn.execute("SELECT id FROM creatures WHERE name = 'Eevee'").fetchone()[0]
            pikachu_id = conn.execute("SELECT id FROM creatures WHERE name = 'Pikachu'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P10', ?, 'evouser', ?, 10, 0, ?, 0, 0, 1000)
                """,
                (u_id, eevee_id, int(time.time()))
            )
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P11', ?, 'evouser', ?, 10, 0, ?, 0, 0, 1000)
                """,
                (u_id, pikachu_id, int(time.time()))
            )
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'water-stone', 1)", (u_id,))
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'thunder-stone', 1)", (u_id,))

        use_water = engine.use("evouser", "water-stone", "P10")
        assert "Vaporeon" in use_water

        use_thunder = engine.use("evouser", "thunder-stone", "P11")
        assert "Raichu" in use_thunder
        close_loggers()


def test_active_state_helpers():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        assert not engine._is_battle_active()
        assert not engine._is_trade_active()

        # Expire pending battles helper
        with db_session(engine.paths) as conn:
            engine._expire_pending_battles(conn)
        close_loggers()


def test_inventory_grid_image_generation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        out_path = engine._generate_inventory_grid_image("testuser", {1, 25}, {1: 2, 25: 1})
        assert out_path.exists()
        close_loggers()


def test_discord_webhooks_mock(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.settings["discord_inventory_webhook_url"] = "http://example.com/webhook"

        # Mock urllib urlopen for webhook success
        class MockResponse:
            def read(self):
                return json.dumps({"id": "123", "channel_id": "456", "guild_id": "789"}).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        import game_engine
        monkeypatch.setattr(game_engine, "urlopen", lambda *args, **kwargs: MockResponse())

        fake_png = Path(tmp) / "fake.png"
        fake_png.write_bytes(b"PNGDATA")

        url = engine._send_discord_inventory_image_webhook("user1", fake_png, "stats text")
        assert "discord.com" in url

        url_stats = engine._send_discord_stats_webhook("Stats content")
        assert "discord.com" in url_stats
        close_loggers()


def test_inventory_command_with_owned_pokemon():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "invuser")
            c_id = conn.execute("SELECT id FROM creatures WHERE name = 'Charmander'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P99', ?, 'invuser', ?, 5, 0, ?, 2, 1, 1050)
                """,
                (u_id, c_id, int(time.time()))
            )
            conn.execute("INSERT INTO pokedex (user_id, creature_id) VALUES (?, ?)", (u_id, c_id))

        res = engine.inventory("invuser")
        assert "invuser" in res
        close_loggers()


def test_evolution_prompts_and_lucky_xp():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        with db_session(engine.paths) as conn:
            u_id = engine._ensure_user(conn, "luckyuser")
            eevee_id = conn.execute("SELECT id FROM creatures WHERE name = 'Eevee'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, trait, elo)
                VALUES ('P100', ?, 'luckyuser', ?, 10, 0, ?, 0, 0, 'Lucky', 1000)
                """,
                (u_id, eevee_id, int(time.time()))
            )
            prompts = engine._check_ready_to_evolve_prompt(conn, "luckyuser")
            assert len(prompts) > 0

            # Award XP to lucky user
            engine._award_battle_xp(conn, "P100", 500, is_winner=True)
            row = conn.execute("SELECT level, wins FROM inventory WHERE id = 'P100'").fetchone()
            assert row[1] == 1  # 1 win added
        close_loggers()


def test_battle_simulation_critical_and_miss_mechanics():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.settings["miss_chance"] = 1.0  # Force miss
        
        p1 = BattlePokemon(
            inv_id="P1", owner="u1", name="Pikachu", level=5, xp=0, trait="Swift",
            elo=1000, wins=0, losses=0, hp_iv=10, atk_iv=10, def_iv=10, spd_iv=10,
            base_hp=35, base_attack=55, base_defense=40, base_speed=90, base_sp_atk=50, base_sp_def=50,
            types=["Electric"], creature_id=25
        )
        p2 = BattlePokemon(
            inv_id="P2", owner="u2", name="Geodude", level=5, xp=0, trait="Tank",
            elo=1000, wins=0, losses=0, hp_iv=10, atk_iv=10, def_iv=10, spd_iv=10,
            base_hp=40, base_attack=80, base_defense=100, base_speed=20, base_sp_atk=30, base_sp_def=30,
            types=["Rock", "Ground"], creature_id=74
        )

        engine.rng.seed(1)
        transcript, log, winner = engine._simulate_battle(p1, p2)
        assert any("missed" in t for t in transcript)
        close_loggers()
