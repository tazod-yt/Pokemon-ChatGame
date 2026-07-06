import requests
import json
from collections import defaultdict

BASE_URL = "https://pokeapi.co/api/v2"

# Get species info for Pokemon 1-151
species_cache = {}

for pokemon_id in range(1, 152):
    response = requests.get(f"{BASE_URL}/pokemon-species/{pokemon_id}")
    response.raise_for_status()
    data = response.json()

    species_cache[data["name"]] = {
        "id": pokemon_id,
        "evolution_chain_url": data["evolution_chain"]["url"]
    }

evolution_data = defaultdict(list)
processed_chains = set()


def process_chain(chain):
    current_name = chain["species"]["name"]

    for evo in chain["evolves_to"]:
        target_name = evo["species"]["name"]

        evo_info = {
            "to": target_name,
            "type": None
        }

        if evo["evolution_details"]:
            details = evo["evolution_details"][0]

            trigger = details["trigger"]["name"]
            evo_info["type"] = trigger

            if details["min_level"] is not None:
                evo_info["level"] = details["min_level"]

            if details["item"]:
                evo_info["item"] = details["item"]["name"]

            if details["min_happiness"]:
                evo_info["friendship"] = details["min_happiness"]

            if details["held_item"]:
                evo_info["held_item"] = details["held_item"]["name"]

            if details["time_of_day"]:
                evo_info["time_of_day"] = details["time_of_day"]

            if details["known_move"]:
                evo_info["known_move"] = details["known_move"]["name"]

        evolution_data[current_name].append(evo_info)

        process_chain(evo)


for species_name, info in species_cache.items():
    chain_url = info["evolution_chain_url"]

    if chain_url in processed_chains:
        continue

    processed_chains.add(chain_url)

    chain_response = requests.get(chain_url)
    chain_response.raise_for_status()

    chain_json = chain_response.json()

    process_chain(chain_json["chain"])

# Convert names to title case
result = {}

for pokemon_name, evolutions in evolution_data.items():
    result[pokemon_name.title()] = []

    for evo in evolutions:
        cleaned = evo.copy()
        cleaned["to"] = cleaned["to"].title()
        result[pokemon_name.title()].append(cleaned)

with open("gen1_evolutions.json", "w") as f:
    json.dump(result, f, indent=2)

print("Saved gen1_evolutions.json")