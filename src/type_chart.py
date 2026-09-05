TYPE_CHART = {
    "Normal": {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire": {"Grass": 2, "Ice": 2, "Bug": 2, "Steel": 2, "Fire": 0.5, "Water": 0.5, "Rock": 0.5, "Dragon": 0.5},
    "Water": {"Fire": 2, "Ground": 2, "Rock": 2, "Water": 0.5, "Grass": 0.5, "Dragon": 0.5},
    "Electric": {"Water": 2, "Flying": 2, "Electric": 0.5, "Grass": 0.5, "Dragon": 0.5, "Ground": 0},
    "Grass": {"Water": 2, "Ground": 2, "Rock": 2, "Fire": 0.5, "Grass": 0.5, "Poison": 0.5, "Flying": 0.5, "Bug": 0.5, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Grass": 2, "Ground": 2, "Flying": 2, "Dragon": 2, "Fire": 0.5, "Water": 0.5, "Ice": 0.5, "Steel": 0.5},
    "Fighting": {"Normal": 2, "Ice": 2, "Rock": 2, "Dark": 2, "Steel": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Fairy": 0.5, "Ghost": 0},
    "Poison": {"Grass": 2, "Fairy": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0},
    "Ground": {"Fire": 2, "Electric": 2, "Poison": 2, "Rock": 2, "Steel": 2, "Grass": 0.5, "Bug": 0.5, "Flying": 0},
    "Flying": {"Grass": 2, "Fighting": 2, "Bug": 2, "Electric": 0.5, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Steel": 0.5, "Dark": 0},
    "Bug": {"Grass": 2, "Psychic": 2, "Dark": 2, "Fire": 0.5, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Ghost": 0.5, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2, "Ice": 2, "Flying": 2, "Bug": 2, "Fighting": 0.5, "Ground": 0.5, "Steel": 0.5},
    "Ghost": {"Psychic": 2, "Ghost": 2, "Dark": 0.5, "Normal": 0},
    "Dragon": {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
    "Dark": {"Psychic": 2, "Ghost": 2, "Fighting": 0.5, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Ice": 2, "Rock": 2, "Fairy": 2, "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Steel": 0.5},
    "Fairy": {"Fighting": 2, "Dragon": 2, "Dark": 2, "Fire": 0.5, "Poison": 0.5, "Steel": 0.5},
}


def get_type_multiplier(attack_type: str, defender_types: list) -> float:
    multiplier = 1.0
    if not attack_type or not isinstance(attack_type, str):
        return 1.0
    atk_clean = attack_type.strip().capitalize()
    chart = TYPE_CHART.get(atk_clean, {})
    for d in defender_types or []:
        if isinstance(d, str):
            d_clean = d.strip().capitalize()
            multiplier *= chart.get(d_clean, 1.0)
        else:
            multiplier *= chart.get(d, 1.0)
    return multiplier


def get_type_weaknesses(defender_types: list) -> list[tuple[str, float]]:
    """Return a list of (attack_type, multiplier) where multiplier > 1.0 for the given defender types.
    Sorted by multiplier descending, then attack type name ascending."""
    if not defender_types:
        return []
    weaknesses: list[tuple[str, float]] = []
    for atk_type in TYPE_CHART.keys():
        mult = get_type_multiplier(atk_type, defender_types)
        if mult > 1.0:
            weaknesses.append((atk_type, mult))
    weaknesses.sort(key=lambda item: (-item[1], item[0]))
    return weaknesses


def format_type_weaknesses(defender_types: list) -> str:
    """Format weaknesses into a human-readable string, e.g. 'Rock (4x), Electric (2x), Water (2x)'."""
    weaknesses = get_type_weaknesses(defender_types)
    if not weaknesses:
        return "None"
    return ", ".join(f"{atk} ({int(mult) if mult.is_integer() else mult}x)" for atk, mult in weaknesses)
