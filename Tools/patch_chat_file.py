import pathlib

path = pathlib.Path(r"Pokemon ChatGame\src\game_engine.py")
text = path.read_text(encoding="utf-8")
block = """    if not paths.overlay_state_json.exists():
        write_json(
            paths.overlay_state_json,
            {
                \"state\": \"idle\",
                \"message\": \"\",
                \"spawn\": None,
                \"timer\": 0,
                \"result\": None,
                \"updated_at\": None,
            },
        )
"""
insert = block + "    if not paths.chat_message_txt.exists():\n        paths.chat_message_txt.write_text(\"\", encoding=\"utf-8\")\n"
if block in text and "chat_message_txt" not in text:
    text = text.replace(block, insert)
elif "chat_message_txt" not in text:
    # fallback: insert before def set_setting
    text = text.replace("\n\n\n\ndef set_setting", "\n    if not paths.chat_message_txt.exists():\n        paths.chat_message_txt.write_text(\"\", encoding=\"utf-8\")\n\n\n\ndef set_setting")

path.write_text(text, encoding="utf-8")
print("Inserted chat_message_txt creation")
