import pathlib

path = pathlib.Path(r"Pokemon ChatGame\src\game_engine.py")
text = path.read_text(encoding="utf-8")
needle = "        settings_json=config_dir / \"settings.json\",\n        log_file=logs_dir / \"game.log\",\n    )\n"
insert = "        settings_json=config_dir / \"settings.json\",\n        log_file=logs_dir / \"game.log\",\n        chat_message_txt=data_dir / \"last_chat_message.txt\",\n    )\n"
if needle in text and "last_chat_message.txt" not in text:
    text = text.replace(needle, insert)

path.write_text(text, encoding="utf-8")
print("Inserted chat_message_txt in build_paths")
