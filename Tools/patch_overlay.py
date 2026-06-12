import pathlib

path = pathlib.Path(r"Pokemon ChatGame\src\game_engine.py")
text = path.read_text(encoding="utf-8")

old_success = """                self._write_overlay(
                    {
                        \"state\": \"result\",
                        \"message\": f\"{username} caught {spawn.get('name', 'a creature')}!\",
                        \"spawn\": None,
                        \"timer\": 0,
                        \"result\": {
                            \"type\": \"catch_success\",
                            \"user\": username,
                            \"creature\": spawn.get(\"name\"),
                        },
                    }
                )
"""

new_success = """                self._write_overlay(
                    {
                        \"state\": \"idle\",
                        \"message\": \"\",
                        \"spawn\": None,
                        \"timer\": 0,
                        \"result\": None,
                    }
                )
"""

old_fail = """            self._write_overlay(
                {
                    \"state\": \"result\",
                    \"message\": f\"{username} failed to catch {spawn.get('name', 'the creature')}\",
                    \"spawn\": spawn,
                    \"timer\": max(0, int(spawn.get(\"expires_at\", now)) - now),
                    \"result\": {
                        \"type\": \"catch_fail\",
                        \"user\": username,
                        \"creature\": spawn.get(\"name\"),
                    },
                }
            )
"""

new_fail = """            self._write_overlay(
                {
                    \"state\": \"spawn\",
                    \"message\": \"\",
                    \"spawn\": spawn,
                    \"timer\": max(0, int(spawn.get(\"expires_at\", now)) - now),
                    \"result\": None,
                }
            )
"""

old_battle = """        self._write_overlay(
            {
                \"state\": \"result\",
                \"message\": f\"{winner} wins the battle!\",
                \"spawn\": None,
                \"timer\": 0,
                \"result\": {
                    \"type\": \"battle\",
                    \"winner\": winner,
                    \"loser\": user2 if winner == user1 else user1,
                },
            }
        )
"""

new_battle = """        self._write_overlay(
            {
                \"state\": \"idle\",
                \"message\": \"\",
                \"spawn\": None,
                \"timer\": 0,
                \"result\": None,
            }
        )
"""

if old_success not in text:
    raise SystemExit("Could not find success block to replace")
if old_fail not in text:
    raise SystemExit("Could not find fail block to replace")
if old_battle not in text:
    raise SystemExit("Could not find battle block to replace")

text = text.replace(old_success, new_success)
text = text.replace(old_fail, new_fail)
text = text.replace(old_battle, new_battle)

path.write_text(text, encoding="utf-8")
print("Updated overlay behavior in game_engine.py")
