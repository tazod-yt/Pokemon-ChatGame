import pathlib
import re

path = pathlib.Path(r"Pokemon ChatGame\src\game_engine.py")
text = path.read_text(encoding="utf-8")

# 1) Add chat_message_txt to Paths dataclass
if "chat_message_txt" not in text:
    text = text.replace(
        "    overlay_state_json: Path\n    settings_json: Path\n    log_file: Path\n",
        "    overlay_state_json: Path\n    settings_json: Path\n    log_file: Path\n    chat_message_txt: Path\n",
    )

# 2) Add chat_message_txt in build_paths
if "chat_message_txt" not in text:
    text = text.replace(
        "        overlay_state_json=data_dir / \"overlay_state.json\",\n        settings_json=config_dir / \"settings.json\",\n        log_file=logs_dir / \"game.log\",\n    )\n",
        "        overlay_state_json=data_dir / \"overlay_state.json\",\n        settings_json=config_dir / \"settings.json\",\n        log_file=logs_dir / \"game.log\",\n        chat_message_txt=data_dir / \"last_chat_message.txt\",\n    )\n",
    )

# 3) Ensure chat file exists
if "last_chat_message.txt" not in text:
    text = text.replace(
        "    if not paths.overlay_state_json.exists():\n        write_json(\n",
        "    if not paths.overlay_state_json.exists():\n        write_json(\n",
    )
    insert_marker = "        )\n"
    block = "    if not paths.chat_message_txt.exists():\n        paths.chat_message_txt.write_text(\"\", encoding=\"utf-8\")\n"
    # insert after overlay_state_json block
    pattern = "    if not paths.overlay_state_json.exists():\n        write_json\(\n            paths.overlay_state_json,\n            \{\n                \"state\": \"idle\",\n                \"message\": \"\",\n                \"spawn\": None,\n                \"timer\": 0,\n                \"result\": None,\n                \"updated_at\": None,\n            \},\n        \)\n"
    if re.search(pattern, text):
        text = re.sub(pattern, lambda m: m.group(0) + "\n" + block, text)

# 4) Add helper methods
if "def _write_chat_message" not in text:
    text = text.replace(
        "    def _write_overlay(self, payload: Dict[str, Any]) -> None:\n        payload = dict(payload)\n        payload[\"updated_at\"] = now_ts()\n        write_json(self.paths.overlay_state_json, payload)\n\n",
        "    def _write_overlay(self, payload: Dict[str, Any]) -> None:\n        payload = dict(payload)\n        payload[\"updated_at\"] = now_ts()\n        write_json(self.paths.overlay_state_json, payload)\n\n    def _write_chat_message(self, message: str) -> None:\n        try:\n            self.paths.chat_message_txt.write_text(message, encoding=\"utf-8\")\n        except Exception:\n            logging.exception(\"Failed to write chat message\")\n\n    def _respond(self, message: str) -> str:\n        self._write_chat_message(message)\n        return message\n\n",
    )

# Helper to replace return "..." with return self._respond("...")
replacements = {
    "return f\"Spawn already active: {spawn.get('name', 'Unknown')}\"": "return self._respond(f\"Spawn already active: {spawn.get('name', 'Unknown')}\")",
    "return f\"Spawn on cooldown. Try again in {remaining}s.\"": "return self._respond(f\"Spawn on cooldown. Try again in {remaining}s.\")",
    "return f\"Spawned {creature['name']}\"": "return self._respond(f\"Spawned {creature['name']}\")",
    "return \"Invalid username.\"": "return self._respond(\"Invalid username.\")",
    "return \"No active spawn to catch.\"": "return self._respond(\"No active spawn to catch.\")",
    "return f\"Catch cooldown active. Try again in {remaining}s.\"": "return self._respond(f\"Catch cooldown active. Try again in {remaining}s.\")",
    "return \"Inventory full.\"": "return self._respond(\"Inventory full.\")",
    "return \"Spawn creature missing.\"": "return self._respond(\"Spawn creature missing.\")",
    "return f\"{username} caught {spawn.get('name')}!\"": "return self._respond(f\"{username} caught {spawn.get('name')}!\")",
    "return f\"{username} failed to catch {spawn.get('name')}.\"": "return self._respond(f\"{username} failed to catch {spawn.get('name')}.\")",
    "return f\"{username} has no creatures yet.\"": "return self._respond(f\"{username} has no creatures yet.\")",
    "return \"Invalid battle participants.\"": "return self._respond(\"Invalid battle participants.\")",
    "return f\"Battle cooldown active. Try again in {remaining}s.\"": "return self._respond(f\"Battle cooldown active. Try again in {remaining}s.\")",
    "return \"Both users need at least one creature to battle.\"": "return self._respond(\"Both users need at least one creature to battle.\")",
    "return f\"{winner} wins the battle!\"": "return self._respond(f\"{winner} wins the battle!\")",
    "return \"Spawn reset.\"": "return self._respond(\"Spawn reset.\")",
}

for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)

# inventory return at end
if "return \"\\n\".join(lines)" in text:
    text = text.replace("return \"\\n\".join(lines)", "return self._respond(\"\\n\".join(lines))")

path.write_text(text, encoding="utf-8")
print("Updated game_engine.py with chat output file support")
