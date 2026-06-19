# Battle Logic Redesign Todo

## Goal
Update the battle system so battles become explicit challenge/accept flows with richer Pokémon stats, traits, XP, leveling, evolution, and ELO.

## 1. New battle command flow
- Change `!battle` to require: `!battle @user <pokemon name or number>`
- The challenger selects a specific Pokémon from their inventory.
- The challenged user must accept with: `!accept <pokemon name or number>`
- Only after `!accept` should the battle begin.
- Track pending battles in the database using a new pending battles table with challenger, challenged, selected creature inventory IDs, timestamps, status, and rematch/cooldown enforcement.

## 2. Pokémon data model updates
- Extend inventory data with:
  - `level`
  - `xp`
  - `wins`
  - `losses`
  - `hp_iv`, `atk_iv`, `def_iv`, `spd_iv`
  - `trait`
  - `elo`
  - `species` or maintain `creature_id` to reference base species stats.
- Continue using `creature_id` as the species reference, while storing per-caught stats in inventory.
- Assign `trait` equally randomly when a Pokémon is caught.
- Ensure default `elo = 1000` for new catches.

## 3. Trait system
- Add trait bonuses:
  - `Brave`: attack * 1.10
  - `Tank`: defense * 1.10
  - `Swift`: speed * 1.10
  - `Lucky`: xp * 1.15
  - `Berserk`: crit_chance + 0.15
- Base critical chance: `CRIT_CHANCE = 0.10`

## 4. Derived stats
- Compute battle stats per Pokémon using base stats + level + IVs:
  - `hp = base_hp + level * 3 + hp_iv`
  - `attack = base_attack + level * 2 + atk_iv`
  - `defense = base_defense + level * 2 + def_iv`
  - `speed = base_speed + level * 1.5 + spd_iv`
- Apply trait bonuses to attack/defense/speed.
- If needed, add `sp_atk` / `sp_def` handling later for attack style.

## 5. Battle flow and turn order
- Determine first attacker by higher derived speed.
- Each turn:
  - 10% critical chance: multiply damage by 1.5
  - 5% miss chance: damage = 0
- Damage formula:
  - `damage = (attacker.attack * random.uniform(0.9, 1.1)) - (defender.defense * 0.5)`
  - `damage = max(5, int(damage))`
- Subtract damage from target HP and log messages until one Pokémon hits 0 HP.

## 6. Battle messages
- Display a screen/overlay-facing battle transcript with messages such as:
  - `⚡ Pikachu attacks for 22 damage`
  - `🌿 Bulbasaur attacks for 18 damage`
  - `⚡ Critical hit!`
  - `🌿 Bulbasaur fainted`
  - `🏆 Pikachu wins`
- Use the chosen Pokémon and user names in the screen summary output.
- Write the battle transcript into overlay state or screen state, not just chat.

## 7. XP and leveling
- XP gains:
  - Winner: `50 + opponent_level * 5`
  - Loser: `15 + opponent_level * 2`
- Apply Lucky trait bonus: `xp_gain *= 1.15`
- Update `wins` / `losses` counters.
- Level up:
  - `xp_required = level * 100`
  - `while xp >= level * 100: xp -= level * 100; level += 1`
  - Cap at `MAX_LEVEL = 100`
- Update current HP after leveling, e.g. `current_hp = base_hp + level * 5` or derived formula.

## 8. Evolution
- After battle, evaluate species evolution thresholds using `evolution_rules.json`.
- Example mappings:
  - `Charmander -> Charmeleon` at level >= 16
  - `Charmeleon -> Charizard` at level >= 36
  - `Bulbasaur -> Ivysaur` at level >= 16
  - `Ivysaur -> Venusaur` at level >= 32
- Add more species to `evolution_rules.json` as needed.

## 9. ELO system
- Maintain `elo` per captured Pokémon.
- Battle result:
  - Winner: `elo += 25`
  - Loser: `elo -= 20`
  - Clamp to minimum `0`

## 10. Leaderboards
- Add leaderboard query for strongest Pokémon sorted by `elo DESC`.
- Format output like: `1. Dragonite (Ankit) 1450`

## 11. Battle cooldowns
- Enforce `BATTLE_COOLDOWN = 60 seconds`
- Enforce `REMATCH_COOLDOWN = 5 minutes` between same players
- Store timestamps for last battle and last same-opponent battle.

## 12. Integration decisions
- Persist challenge/accept state in the database using a new pending battles table.
- Inventory details are stored in the `inventory` table, so add IV/trait/elo fields there.
- Keep `creature_id` as the species reference; this is the canonical meaning of "species" in the current schema.
- Do not persist battle HP between fights; each battle uses derived max HP and resets per encounter.
- Assign traits equally randomly on catch.
- Do not implement moves/types now; use stat-based attack behavior instead.

## 13. Implementation notes
- Existing battle logic is in `src/game_engine.py`.
- Likely changes required in:
  - battle command parsing
  - battle state persistence
  - `_simulate_battle()` and experience/level handling
  - catch logic to assign trait and IVs
  - unit tests in `tests/test_game_engine.py`

## Open question for review
Please confirm:
- Want challenge/accept flow persisted across process restarts?
- Should battle use only selected single Pokémon, or allow later multi-Pokémon teams?
- Do we want to leave type/move logic out and use stat-based attack style as suggested?
- Should the new trait and IV fields be added to the `creatures` table, `inventory` table, or a new joined table?
