import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from game_engine import (  # noqa: E402
    GameEngine,
    build_paths,
    compute_derived_hp,
    compute_derived_stats,
    db_session,
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
    settings["discord_inventory_webhook_url"] = ""  # Disable webhooks in tests
    init_db(paths)
    seed_creatures(paths)
    ensure_data_files(paths)
    return GameEngine(paths, settings)


def catch_for_user(engine: GameEngine, username: str, base_seed: int = 1) -> None:
    start = base_seed * 1000
    for seed in range(start, start + 500):
        with db_session(engine.paths) as conn:
            conn.execute("DELETE FROM settings WHERE key = 'last_spawn_at'")
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET last_catch_at = NULL WHERE id = ?", (row[0],)
                )
        engine.rng.seed(seed)
        engine.spawn()
        engine.rng.seed(seed)
        result = engine.catch(username)
        if "caught" in result:
            return
        engine.reset_spawn()
    raise RuntimeError(f"Could not catch pokemon for {username}")


def test_spawn_creation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        result = engine.spawn()
        assert "appeared" in result


def test_catch_success():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "ankit" in result


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
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "ankit" in result
        assert "ELO" in result


def test_inventory_item_includes_username():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "Pokedex:" in result
        assert "HP" in result
        assert "ELO" in result


def test_battle_challenge_and_accept():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "user1", 1)
        catch_for_user(engine, "user2", 2)

        with db_session(engine.paths) as conn:
            challenger_pid = conn.execute(
                "SELECT inventory.id FROM inventory JOIN users ON users.id = inventory.user_id WHERE users.username = ? ORDER BY inventory.obtained_at LIMIT 1",
                ("user1",),
            ).fetchone()[0]
            accepter_pid = conn.execute(
                "SELECT inventory.id FROM inventory JOIN users ON users.id = inventory.user_id WHERE users.username = ? ORDER BY inventory.obtained_at LIMIT 1",
                ("user2",),
            ).fetchone()[0]

        challenge = engine.battle("user1", "user2", challenger_pid)
        assert "challenged" in challenge

        result = engine.accept("user2", "user1", accepter_pid)
        assert "wins" in result.lower()


def test_leaderboard():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.leaderboard()
        assert "Top" in result and "ELO" in result
        assert "ankit" in result


def test_derived_stats():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ensure_dirs(build_paths(tmp_path))
        settings = load_settings(build_paths(tmp_path))
        hp = compute_derived_hp(45, 10, 5)
        assert hp == 45 + 30 + 5
        atk, defense, speed = compute_derived_stats(49, 49, 45, 10, 5, 5, 5, "Brave", settings)
        assert atk > 49
        assert defense == 49 + 20 + 5


def test_data_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = make_engine(root)
        catch_for_user(engine, "ankit", 1)
        engine2 = make_engine(root)
        result = engine2.inventory("ankit")
        assert "ankit" in result


def test_load_settings_streamerbot_globals_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STREAMERBOT_SPAWN_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("STREAMERBOT_COOLDOWN_SECONDS", "7")

    paths = build_paths(tmp_path)
    ensure_dirs(paths)
    paths.settings_json.write_text(
        json.dumps({"spawn_interval_seconds": 5, "cooldown_seconds": 2}),
        encoding="utf-8",
    )

    settings = load_settings(paths)

    assert settings["spawn_interval_seconds"] == 5
    assert settings["cooldown_seconds"] == 2


def test_pokedex_caught_and_evolved_species():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # 1. Catch a Bulbasaur for "ankit"
        catch_for_user(engine, "ankit", 1)
        
        # Verify it exists in pokedex
        with db_session(engine.paths) as conn:
            user_id = conn.execute("SELECT id FROM users WHERE username = 'ankit'").fetchone()[0]
            inv_row = conn.execute(
                "SELECT creatures.name, inventory.id FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            assert inv_row is not None
            inv_id = inv_row[1]
            
            # Force it to be "Bulbasaur" to test level-up rule
            bulbasaur_id = conn.execute("SELECT id FROM creatures WHERE name = 'Bulbasaur'").fetchone()[0]
            conn.execute("UPDATE inventory SET creature_id = ? WHERE id = ?", (bulbasaur_id, inv_id))
            
            # Insert Bulbasaur into pokedex (migration/catch logic usually does this)
            conn.execute("INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)", (user_id, bulbasaur_id))

        # 2. Check that pokedex reflects Bulbasaur in database
        with db_session(engine.paths) as conn:
            pokedex_count = conn.execute(
                "SELECT COUNT(*) FROM pokedex WHERE user_id = ? AND creature_id = ?",
                (user_id, bulbasaur_id)
            ).fetchone()[0]
            assert pokedex_count == 1

        # 3. Simulate level-up evolution (level 16)
        with db_session(engine.paths) as conn:
            # Set level of our pokemon to 16
            conn.execute("UPDATE inventory SET level = 16 WHERE id = ?", (inv_id,))
            
            # Retrieve pokemon details as BattlePokemon to run check_evolution
            from game_engine import BattlePokemon
            p_row = conn.execute(
                "SELECT level, xp, trait, elo, wins, losses, hp_iv, atk_iv, def_iv, spd_iv, base_hp, base_attack, base_defense, base_speed, base_sp_atk, base_sp_def, types, creature_id FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
                (inv_id,)
            ).fetchone()
            
            battle_pokemon = BattlePokemon(
                inv_id=inv_id,
                owner="ankit",
                name="Bulbasaur",
                level=p_row[0],
                xp=p_row[1],
                trait=p_row[2],
                elo=p_row[3],
                wins=p_row[4],
                losses=p_row[5],
                hp_iv=p_row[6],
                atk_iv=p_row[7],
                def_iv=p_row[8],
                spd_iv=p_row[9],
                base_hp=p_row[10],
                base_attack=p_row[11],
                base_defense=p_row[12],
                base_speed=p_row[13],
                base_sp_atk=p_row[14],
                base_sp_def=p_row[15],
                types=json.loads(p_row[16]),
                creature_id=p_row[17]
            )
            
            # Trigger evolution check
            evolves_to = engine._check_evolution(conn, battle_pokemon)
            assert evolves_to == "Ivysaur"
            
            # Verify inventory is updated to Ivysaur
            new_inv_row = conn.execute(
                "SELECT creatures.name FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
                (inv_id,)
            ).fetchone()
            assert new_inv_row[0] == "Ivysaur"
            
            # Verify BOTH Bulbasaur and Ivysaur exist in the pokedex table!
            bulbasaur_id = conn.execute("SELECT id FROM creatures WHERE name = 'Bulbasaur'").fetchone()[0]
            ivysaur_id = conn.execute("SELECT id FROM creatures WHERE name = 'Ivysaur'").fetchone()[0]
            
            assert conn.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ? AND creature_id = ?", (user_id, bulbasaur_id)).fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM pokedex WHERE user_id = ? AND creature_id = ?", (user_id, ivysaur_id)).fetchone()[0] == 1


def test_items_trading_and_evolution():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # 1. Setup users
        with db_session(engine.paths) as conn:
            user1_id = engine._ensure_user(conn, "ankit")
            user2_id = engine._ensure_user(conn, "tazod")
            
            # Catch an Eevee for ankit
            eevee_id = conn.execute("SELECT id FROM creatures WHERE name = 'Eevee'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'ankit', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (user1_id, eevee_id, int(time.time()))
            )
            eevee_pid = "P1"
            
            # Catch a Growlithe for tazod
            growlithe_id = conn.execute("SELECT id FROM creatures WHERE name = 'Growlithe'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P2', ?, 'tazod', ?, 10, 0, ?, 0, 0, 1000)
                """,
                (user2_id, growlithe_id, int(time.time()))
            )
            growlithe_pid = "P2"

        # 2. Check empty bag
        bag_output = engine.bag("ankit")
        assert "empty" in bag_output
        
        # 3. Add item and check bag
        with db_session(engine.paths) as conn:
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'fire-stone', 1)", (user1_id,))
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'fire-stone', 1)", (user2_id,))
            
        bag_output = engine.bag("ankit")
        assert "1x fire-stone" in bag_output
        
        # 4. Try to use stone under level 10 (Eevee is level 1)
        use_output = engine.use("ankit", "fire-stone", str(eevee_pid))
        assert "Level 10" in use_output
        
        # Set Eevee level to 10
        with db_session(engine.paths) as conn:
            conn.execute("UPDATE inventory SET level = 10 WHERE id = ?", (eevee_pid,))
            
        # Use fire-stone on Eevee (should succeed and evolve to Flareon)
        use_output = engine.use("ankit", "fire-stone", str(eevee_pid))
        assert "evolving it into Flareon" in use_output
        
        with db_session(engine.paths) as conn:
            creature_name = conn.execute(
                "SELECT name FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
                (eevee_pid,)
            ).fetchone()[0]
            assert creature_name == "Flareon"
            
            # Check item is consumed
            qty = conn.execute("SELECT quantity FROM bag WHERE user_id = ? AND item_name = 'fire-stone'", (user1_id,)).fetchone()[0]
            assert qty == 0

        # 5. Test trade offers
        trade_output = engine.trade("ankit", "tazod", str(eevee_pid))
        assert "wants to trade" in trade_output
        
        # Accept trade
        accept_output = engine.accepttrade("tazod", "ankit", str(growlithe_pid))
        assert "Trade complete" in accept_output
        
        with db_session(engine.paths) as conn:
            # Check ownership swapped
            owner1 = conn.execute("SELECT username FROM inventory WHERE id = ?", (eevee_pid,)).fetchone()[0]
            owner2 = conn.execute("SELECT username FROM inventory WHERE id = ?", (growlithe_pid,)).fetchone()[0]
            assert owner1 == "tazod"
            assert owner2 == "ankit"

        # 6. Test trade with item evolution
        # Tazod has a metal-coat. ankit catches Onix and trades to tazod. Onix should evolve to Steelix.
        with db_session(engine.paths) as conn:
            # Temporarily insert Steelix into creatures table for trade-item evolution validation
            conn.execute(
                """
                INSERT INTO creatures (species_id, name, base_hp, base_attack, base_defense, base_speed, created_at)
                VALUES (208, 'Steelix', 75, 85, 200, 30, ?)
                """,
                (int(time.time()),)
            )
            onix_id = conn.execute("SELECT id FROM creatures WHERE name = 'Onix'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P3', ?, 'ankit', ?, 10, 0, ?, 0, 0, 1000)
                """,
                (user1_id, onix_id, int(time.time()))
            )
            onix_pid = "P3"
            
            # Give metal-coat to tazod (the receiver of Onix)
            conn.execute(
                """
                INSERT INTO bag (user_id, item_name, quantity)
                VALUES (?, 'metal-coat', 1)
                ON CONFLICT(user_id, item_name)
                DO UPDATE SET quantity = quantity + 1
                """,
                (user2_id,)
            )
            
        # Offer trade: ankit offers Onix to tazod
        engine.trade("ankit", "tazod", str(onix_pid))
        
        # tazod accepts with their Flareon (eevee_pid)
        accept_output = engine.accepttrade("tazod", "ankit", str(eevee_pid))
        
        # Check that Onix evolved to Steelix and item is consumed
        assert "evolved into Steelix" in accept_output
        with db_session(engine.paths) as conn:
            onix_species = conn.execute(
                "SELECT name FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
                (onix_pid,)
            ).fetchone()[0]
            assert onix_species == "Steelix"
            
            qty = conn.execute("SELECT quantity FROM bag WHERE user_id = ? AND item_name = 'metal-coat'", (user2_id,)).fetchone()[0]
            assert qty == 0


def test_catch_with_specialty_balls():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # 1. Spawn a wild creature
        engine.spawn()
        
        # 2. Try to catch with great ball without having one in bag (should fail and warn)
        catch_res = engine.catch("ankit", "great")
        assert "do not have any great ball" in catch_res
        
        # 3. Try to catch with ultra ball without having one in bag (should fail and warn)
        catch_res = engine.catch("ankit", "ultra")
        assert "do not have any ultra ball" in catch_res
        
        # 4. Award balls to user
        with db_session(engine.paths) as conn:
            user_id = engine._ensure_user(conn, "ankit")
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'great-ball', 1)", (user_id,))
            conn.execute("INSERT INTO bag (user_id, item_name, quantity) VALUES (?, 'ultra-ball', 1)", (user_id,))
            
        # 5. Catch using specialty ball
        with db_session(engine.paths) as conn:
            conn.execute("UPDATE users SET last_catch_at = 0 WHERE id = ?", (user_id,))
            
        catch_res = engine.catch("ankit", "great")
        # Check that the great-ball was consumed from bag
        with db_session(engine.paths) as conn:
            qty = conn.execute("SELECT quantity FROM bag WHERE user_id = ? AND item_name = 'great-ball'", (user_id,)).fetchone()[0]
            assert qty == 0
            
        # 6. Reset spawn and test catch success multiplier
        engine._write_active_spawn({})
        with db_session(engine.paths) as conn:
            conn.execute("UPDATE settings SET value = '0' WHERE key = 'last_spawn_at'")
        engine.spawn()
        with db_session(engine.paths) as conn:
            conn.execute("UPDATE users SET last_catch_at = 0 WHERE id = ?", (user_id,))
            
        catch_res2 = engine.catch("ankit", "ultra")
        with db_session(engine.paths) as conn:
            qty = conn.execute("SELECT quantity FROM bag WHERE user_id = ? AND item_name = 'ultra-ball'", (user_id,)).fetchone()[0]
            assert qty == 0


def test_trade_by_name_and_number_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # 1. Setup users
        with db_session(engine.paths) as conn:
            user1_id = engine._ensure_user(conn, "ankit")
            user2_id = engine._ensure_user(conn, "tazod")
            
            eevee_id = conn.execute("SELECT id FROM creatures WHERE name = 'Eevee'").fetchone()[0]
            growlithe_id = conn.execute("SELECT id FROM creatures WHERE name = 'Growlithe'").fetchone()[0]
            
            # Catch ONE Eevee for ankit
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P1', ?, 'ankit', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (user1_id, eevee_id, int(time.time()))
            )
            
            # Catch ONE Growlithe for tazod
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P2', ?, 'tazod', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (user2_id, growlithe_id, int(time.time()))
            )
            
        # 2. Trade Eevee by name (should succeed since unique)
        trade_res = engine.trade("ankit", "tazod", "Eevee")
        assert "wants to trade their Eevee (PID: P1)" in trade_res
        
        # 3. accepttrade by name (should succeed since unique)
        accept_res = engine.accepttrade("tazod", "ankit", "Growlithe")
        assert "Trade complete" in accept_res
        assert "found" in accept_res
        
        # Verify drops are in their bags
        with db_session(engine.paths) as conn:
            user1_bag = conn.execute("SELECT COUNT(*) FROM bag WHERE user_id = ?", (user1_id,)).fetchone()[0]
            user2_bag = conn.execute("SELECT COUNT(*) FROM bag WHERE user_id = ?", (user2_id,)).fetchone()[0]
            assert user1_bag > 0
            assert user2_bag > 0
            
        # 4. Catch a second Eevee for tazod (who now also owns P1 Eevee from the trade)
        # So tazod owns both 'P1' (Eevee) and 'P3' (Eevee)
        with db_session(engine.paths) as conn:
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at, wins, losses, elo)
                VALUES ('P3', ?, 'tazod', ?, 1, 0, ?, 0, 0, 1000)
                """,
                (user2_id, eevee_id, int(time.time()))
            )
            
        # 5. Try to trade Eevee by name from tazod (should trigger duplicate warning conflict)
        trade_conflict_res = engine.trade("tazod", "ankit", "Eevee")
        assert "you have more than 1 Eevee use PID instead" in trade_conflict_res
        
        # 6. Try to trade by species ID (133 is Eevee) from tazod (should also trigger conflict)
        trade_conflict_res2 = engine.trade("tazod", "ankit", "133")
        assert "you have more than 1 Eevee use PID instead" in trade_conflict_res2


def test_update_game_already_up_to_date():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        result = engine.update_game()
        assert "Already up to date" in result or "Error checking for updates on GitHub" in result or "Could not retrieve latest release info" in result


def test_trade_locking_and_simulation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        
        # Test simulation CLI command test_trade
        res = engine.test_trade("Tazod", "Ankit", "Charizard", "Blastoise")
        assert "Test trade triggered" in res
        
        # Test _is_trade_active (should be False because test_trade cleaned it up)
        assert not engine._is_trade_active()
        
        # Manually write an active trade state to the overlay state JSON
        engine._write_overlay({
            "state": "trade",
            "trade": {
                "sender": "ankit",
                "receiver": "tazod",
                "sender_pokemon": "Charizard",
                "receiver_pokemon": "Blastoise",
                "expires_at": int(time.time()) + 100,
            }
        })
        
        assert engine._is_trade_active()
        
        # 1. spawn() should fail
        spawn_res = engine.spawn()
        assert "A trade is in progress" in spawn_res
        
        # 2. catch() should fail
        catch_res = engine.catch("ankit")
        assert "A trade is in progress" in catch_res
        
        # 3. battle() should fail
        battle_res = engine.battle("ankit", "tazod", "Charizard")
        assert "A trade is in progress" in battle_res
        
        # 4. accept() should fail
        accept_res = engine.accept("tazod", "ankit", "Blastoise")
        assert "A trade is in progress" in accept_res
        
        # 5. accepttrade() should fail
        accepttrade_res = engine.accepttrade("tazod", "ankit", "Growlithe")
        assert "A trade is in progress" in accepttrade_res
        
        # 6. auto_spawn() should skip (return empty string)
        auto_res = engine.auto_spawn()
        assert auto_res == ""

        # 7. Test stats command prints evolution info
        with db_session(engine.paths) as conn:
            user_id = engine._ensure_user(conn, "ankit")
            eevee_id = conn.execute("SELECT id FROM creatures WHERE name = 'Eevee'").fetchone()[0]
            conn.execute(
                """
                INSERT INTO inventory (id, user_id, username, creature_id, level, xp, obtained_at)
                VALUES ('P99', ?, 'ankit', ?, 10, 0, ?)
                """,
                (user_id, eevee_id, int(time.time()))
            )
            
        stats_res = engine.stats("ankit", "Eevee")
        assert "Jolteon" in stats_res
        assert "Flareon" in stats_res
        assert "Vaporeon" in stats_res
        assert "Evolution Info" in stats_res


