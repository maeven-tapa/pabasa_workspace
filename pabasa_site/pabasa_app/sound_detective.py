"""Curated, server-authoritative content for the Sound Detective template."""

from pathlib import Path

from django.conf import settings


SOUNDS = {
    "English": ["m", "s", "t", "p", "b", "k", "f", "n", "r", "d"],
    "Filipino": ["m", "s", "t", "p", "k"],
}

WORDS = {
    "English": [
        ["moon", "monkey", "lemon", "camel", "jam", "drum"],
        ["sun", "sock", "basket", "whistle", "bus", "mouse"],
        ["table", "tiger", "kitten", "water", "cat", "hat"],
        ["pig", "pizza", "apple", "happy", "cup", "map"],
        ["ball", "banana", "cabbage", "rabbit", "crab", "web"],
        ["kite", "car", "baker", "pocket", "book", "duck"],
        ["fan", "fish", "coffee", "waffle", "leaf", "wolf"],
        ["nest", "nose", "banana", "window", "pen", "sun (2)"],
        ["rabbit", "rainbow", "carrot", "parrot", "car", "star"],
        ["dog", "door", "candy", "rider", "bed", "bird"],
    ],
    "Filipino": [
        ["mata", "mesa", "kamay", "kamatis", "itim", "ulam"],
        ["sabon", "susi", "baso", "keso", "pulis", "walis"],
        ["tali", "tasa", "bata", "pito", "langit", "itik"],
        ["palaka", "puno", "lapis", "ipis", "yakap", "isip"],
        ["kape", "kubo", "buko", "suka", "itik", "manok"],
    ],
}

# The Filipino /t/ set reuses the existing duck illustration stored with Set 5.
IMAGE_OVERRIDES = {
    ("Filipino", 3, "itik"): "pabasa_app/images/sound_detective/filipino/Set_5/itik.png",
}


def catalog():
    result = {}
    positions = ["Beginning", "Beginning", "Middle", "Middle", "End", "End"]
    for language, sounds in SOUNDS.items():
        folder = language.lower()
        sets = []
        for set_index, sound in enumerate(sounds, 1):
            items = []
            for item_index, (asset_word, position) in enumerate(zip(WORDS[language][set_index - 1], positions), 1):
                display_word = "sun" if asset_word == "sun (2)" else asset_word
                filename = f"{asset_word}.png"
                relative = IMAGE_OVERRIDES.get(
                    (language, set_index, asset_word),
                    f"pabasa_app/images/sound_detective/{folder}/Set_{set_index}/{filename}",
                )
                items.append({
                    "id": f"{folder[:2]}_set_{set_index}_{item_index}",
                    "word": display_word,
                    "target_sound": f"/{sound}/",
                    "audio_url": f"/static/pabasa_app/images/sound_detective/audio/{sound}.mp3",
                    "position": position,
                    "image": relative,
                    "image_url": f"/static/{relative}",
                })
            sets.append({"id": f"set_{set_index}", "number": set_index, "sound": f"/{sound}/", "label": f"Set {set_index} — /{sound}/", "items": items})
        result[language] = {"sets": sets}
    return result


def validate_configuration(payload, check_files=True):
    data = payload if isinstance(payload, dict) else {}
    language = str(data.get("language") or "").strip()
    set_id = str(data.get("sound_set") or "").strip()
    selected_ids = data.get("selected_word_ids")
    bank = catalog()
    if language not in bank:
        raise ValueError("Choose English or Filipino.")
    selected_set = next((entry for entry in bank[language]["sets"] if entry["id"] == set_id), None)
    if not selected_set:
        raise ValueError("Choose a sound set for the selected language.")
    if not isinstance(selected_ids, list) or not selected_ids:
        raise ValueError("Select at least one word item.")
    item_map = {item["id"]: item for item in selected_set["items"]}
    if len(set(selected_ids)) != len(selected_ids) or any(item_id not in item_map for item_id in selected_ids):
        raise ValueError("Selected words must belong to the selected sound set.")
    items = [item_map[item_id] for item_id in selected_ids]
    if check_files:
        static_root = Path(settings.BASE_DIR) / "pabasa_app" / "static"
        if any(not (static_root / item["image"]).is_file() for item in items):
            raise ValueError("One or more Sound Detective images could not be found.")
    count = int(data.get("number_of_questions") or len(items))
    if count < 1 or count > len(items):
        raise ValueError("Number of questions cannot exceed the selected words.")
    return {
        "activity_type": "sound_detective", "language": language, "sound_set": set_id,
        "sound_set_label": selected_set["label"], "target_sound": selected_set["sound"],
        "selected_word_ids": selected_ids, "number_of_questions": count,
        "randomize_questions": bool(data.get("randomize_questions")),
        "randomize_answer_choices": bool(data.get("randomize_answer_choices")),
        "allow_retry": data.get("allow_retry") is not False, "items": items,
    }
