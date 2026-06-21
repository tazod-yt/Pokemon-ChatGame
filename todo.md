# Battle Logic Redesign Todo

## Goal
Update the battle system so battles become explicit challenge/accept flows with richer Pokémon stats, traits, XP, leveling, evolution, and ELO.

## 1. New battle command flow
- [x] Change `!battle` to require: `!battle @user <pokemon name or number>`
- [x] The challenger selects a specific Pokémon from their inventory.
- [x] The challenged user must accept with: `!accept @user <pokemon name or number>`
- [x] Only after `!accept` should the battle begin.
- [x] Track pending battles in the database using a new pending battles table with challenger, challenged, selected creature inventory IDs, timestamps, status, and rematch/cooldown enforcement.

## 2. Pokémon data model updates
- [x] Extend inventory data with:
  - `level`
  - `xp` (renamed from `exp`)
  - `wins`
  - `losses`
  - `hp_iv`, `atk_iv`, `def_iv`, `spd_iv`
  - `trait`
  - `elo`
  - `species` or maintain `creature_id` to reference base species stats.
- [x] Continue using `creature_id` as the species reference, while storing per-caught stats in inventory.
- [x] Assign `trait` equally randomly when a Pokémon is caught.
- [x] Ensure default `elo = 1000` for new catches.

## 3. Trait system
- [x] Add trait bonuses:
  - `Brave`: attack * 1.10
  - `Tank`: defense * 1.10
  - `Swift`: speed * 1.10
  - `Lucky`: xp * 1.15
  - `Berserk`: crit_chance + 0.15
- [x] Base critical chance: `CRIT_CHANCE = 0.10`

## 4. Derived stats
- [x] Compute battle stats per Pokémon using base stats + level + IVs:
  - `hp = base_hp + level * 3 + hp_iv`
  - `attack = base_attack + level * 2 + atk_iv`
  - `defense = base_defense + level * 2 + def_iv`
  - `speed = base_speed + level * 1.5 + spd_iv`
- [x] Apply trait bonuses to attack/defense/speed.
- [ ] If needed, add `sp_atk` / `sp_def` handling later for attack style.

## 5. Battle flow and turn order
- [x] Determine first attacker by higher derived speed.
- [x] Each turn:
  - 10% critical chance: multiply damage by 1.5
  - 5% miss chance: damage = 0
- [x] Damage formula:
  - `damage = (attacker.attack * random.uniform(0.9, 1.1)) - (defender.defense * 0.5)`
  - `damage = max(5, int(damage))`
- [x] Subtract damage from target HP and log messages until one Pokémon hits 0 HP.

## 6. Battle messages
- [x] Display a screen/overlay-facing battle transcript with messages such as:
  - `⚡ Pikachu attacks for 22 damage`
  - `🌿 Bulbasaur attacks for 18 damage`
  - `⚡ Critical hit!`
  - `🌿 Bulbasaur fainted`
  - `🏆 Pikachu wins`
- [x] Use the chosen Pokémon and user names in the screen summary output.
- [x] Write the battle transcript into overlay state or screen state, not just chat.

## 7. XP and leveling
- [x] XP gains:
  - Winner: `50 + opponent_level * 5`
  - Loser: `15 + opponent_level * 2`
- [x] Apply Lucky trait bonus: `xp_gain *= 1.15`
- [x] Update `wins` / `losses` counters.
- [x] Level up:
  - `xp_required = level * 100`
  - `while xp >= level * 100: xp -= level * 100; level += 1`
  - Cap at `MAX_LEVEL = 100`
- [x] Battles use fresh derived HP each fight (no persisted battle damage).

## 8. Evolution
- [x] After battle, evaluate species evolution thresholds using `evolution_rules.json`.
- [x] Level-up evolutions from `evolution_rules.json` (e.g. Charmander → Charmeleon at 16).
- [ ] Item/trade/friendship evolutions deferred (rules file includes them for future use).

## 9. ELO system
- [x] Maintain `elo` per captured Pokémon.
- [x] Battle result:
  - Winner: `elo += 25`
  - Loser: `elo -= 20`
  - Clamp to minimum `0`

## 10. Leaderboards
- [x] Add leaderboard query for strongest Pokémon sorted by `elo DESC`.
- [x] Format output like: `1. Dragonite (Ankit) 1450`
- [x] Top 10 entries via `!leaderboard`

## 11. Battle cooldowns
- [x] Enforce `BATTLE_COOLDOWN = 60 seconds`
- [x] Enforce `REMATCH_COOLDOWN = 5 minutes` between same players
- [x] Store timestamps for last battle and last same-opponent battle.

## 12. Integration decisions
- [x] Persist challenge/accept state in the database using a new pending battles table.
- [x] Inventory details are stored in the `inventory` table, so add IV/trait/elo fields there.
- [x] Keep `creature_id` as the species reference; this is the canonical meaning of "species" in the current schema.
- [x] Do not persist battle HP between fights; each battle uses derived max HP and resets per encounter.
- [x] Assign traits equally randomly on catch.
- [x] Do not implement moves/types now; use stat-based attack behavior instead.

## 13. Implementation notes
- [x] Existing battle logic is in `src/game_engine.py`.
- [x] Likely changes required in:
  - battle command parsing
  - battle state persistence
  - `_simulate_battle()` and experience/level handling
  - catch logic to assign trait and IVs
  - unit tests in `tests/test_game_engine.py`
- [x] Streamerbot import updated (`!battle`, `!accept`, `!leaderboard`)

## Future work
- [ ] Overlay battle UI — render battle transcript and animations in `Overlay/` (data is written to `overlay_state.json` today).

## Resolved decisions
- Challenge/accept flow persisted across process restarts (SQLite `pending_battles` table).
- Single Pokémon battles only (1v1 with chosen Pokémon).
- Stat-based combat only; no types/moves for now.
- Trait, IVs, elo, wins/losses on `inventory` table; `base_speed` on `creatures` table.
- IV range 0–15 on catch; `exp` column renamed to `xp`.
- Pending challenges expire after `battle_timeout_seconds` (120s); no separate decline command.
