"""Central, reusable system word bank for syllable-awareness activities."""

from copy import deepcopy


SETS = {
    "Filipino": [
        ("mga_hayop", "Mga Hayop"), ("pagkain", "Pagkain"),
        ("mga_bagay_sa_paligid", "Mga Bagay sa Paligid"), ("kalikasan", "Kalikasan"),
        ("mga_tao_at_lugar", "Mga Tao at Lugar"),
    ],
    "English": [
        ("animals", "Animals"), ("food", "Food"), ("things_around_us", "Things Around Us"),
        ("nature", "Nature"), ("people_and_places", "People & Places"),
    ],
}

# Every entry is (word, syllable parts, difficulty, existing illustrative asset).
_WORDS = {
    "Filipino": {
        "mga_hayop": [("aso", ["a", "so"], "easy", "Set D/Dog.png"), ("pusa", ["pu", "sa"], "easy", "Set D/Cat.png"), ("isda", ["is", "da"], "easy", "Set D/Fish.png"), ("ibon", ["i", "bon"], "easy", "Set D/Bird.png"), ("kuneho", ["ku", "ne", "ho"], "medium", "Set D/Rabbit.png"), ("kabayo", ["ka", "ba", "yo"], "medium", "Set D/Dog.png"), ("kalabaw", ["ka", "la", "baw"], "medium", "Set D/Dog.png"), ("paruparo", ["pa", "ru", "pa", "ro"], "hard", "Set D/Bird.png"), ("pagong", ["pa", "gong"], "medium", "Set D/Rabbit.png"), ("palaka", ["pa", "la", "ka"], "medium", "Set D/Fish.png")],
        "pagkain": [("mangga", ["mang", "ga"], "easy", "Set E/Mango.png"), ("saging", ["sa", "ging"], "easy", "Set E/Banana.png"), ("mansanas", ["man", "sa", "nas"], "medium", "Set E/Apple.png"), ("kahel", ["ka", "hel"], "easy", "Set E/Orange.png"), ("pakwan", ["pak", "wan"], "easy", "Set E/Watermelon.png"), ("kanin", ["ka", "nin"], "easy", "Set A/Fruit.png"), ("tinapay", ["ti", "na", "pay"], "medium", "Set A/Fruit.png"), ("kamatis", ["ka", "ma", "tis"], "medium", "Set A/Fruit.png"), ("gulay", ["gu", "lay"], "easy", "Set A/Fruit.png"), ("tsokolate", ["tso", "ko", "la", "te"], "hard", "Set A/Fruit.png")],
        "mga_bagay_sa_paligid": [("libro", ["li", "bro"], "easy", "Set F/Book.png"), ("mesa", ["me", "sa"], "easy", "Set F/Desk.png"), ("silya", ["sil", "ya"], "easy", "Set F/Chair.png"), ("lapis", ["la", "pis"], "easy", "Set F/Pencil.png"), ("pambura", ["pam", "bu", "ra"], "medium", "Set F/Eraser.png"), ("payong", ["pa", "yong"], "easy", "Set B/Umbrella.png"), ("pitaka", ["pi", "ta", "ka"], "medium", "Set B/Wallet.png"), ("gamot", ["ga", "mot"], "easy", "Set A/Medicine.png"), ("laruan", ["la", "ru", "an"], "medium", "Set B/Robot.png"), ("kuwaderno", ["ku", "wa", "der", "no"], "hard", "Set F/Book.png")],
        "kalikasan": [("araw", ["a", "raw"], "easy", "Set A/Branch.png"), ("ulan", ["u", "lan"], "easy", "Set A/Branch.png"), ("puno", ["pu", "no"], "easy", "Set A/Branch.png"), ("ilog", ["i", "log"], "easy", "Set B/Railway.png"), ("dagat", ["da", "gat"], "easy", "Set D/Fish.png"), ("bulaklak", ["bu", "lak", "lak"], "medium", "Set A/Branch.png"), ("bundok", ["bun", "dok"], "medium", "Set A/Branch.png"), ("bahaghari", ["ba", "hag", "ha", "ri"], "hard", "Set A/Branch.png"), ("hangin", ["ha", "ngin"], "medium", "Set A/Branch.png"), ("kidlat", ["kid", "lat"], "medium", "Set A/Branch.png")],
        "mga_tao_at_lugar": [("guro", ["gu", "ro"], "easy", "Set G/Teacher.png"), ("doktor", ["dok", "tor"], "easy", "Set G/Doctor.png"), ("nars", ["nars"], "easy", "Set G/Nurse.png"), ("pulis", ["pu", "lis"], "easy", "Set G/Police.png"), ("bumbero", ["bum", "be", "ro"], "medium", "Set G/FIrefighter.png"), ("paaralan", ["pa", "a", "ra", "lan"], "hard", "Set F/Desk.png"), ("palengke", ["pa", "leng", "ke"], "medium", "Set A/Fruit.png"), ("ospital", ["os", "pi", "tal"], "medium", "Set G/Doctor.png"), ("simbahan", ["sim", "ba", "han"], "medium", "Set A/Branch.png"), ("aklatan", ["ak", "la", "tan"], "medium", "Set F/Book.png")],
    },
    "English": {
        "animals": [("cat", ["cat"], "easy", "Set D/Cat.png"), ("dog", ["dog"], "easy", "Set D/Dog.png"), ("fish", ["fish"], "easy", "Set D/Fish.png"), ("bird", ["bird"], "easy", "Set D/Bird.png"), ("rabbit", ["rab", "bit"], "easy", "Set D/Rabbit.png"), ("kitten", ["kit", "ten"], "easy", "Set D/Cat.png"), ("monkey", ["mon", "key"], "medium", "Set D/Rabbit.png"), ("tiger", ["ti", "ger"], "medium", "Set D/Cat.png"), ("elephant", ["el", "e", "phant"], "medium", "Set D/Dog.png"), ("butterfly", ["but", "ter", "fly"], "hard", "Set D/Bird.png")],
        "food": [("apple", ["ap", "ple"], "easy", "Set E/Apple.png"), ("mango", ["man", "go"], "easy", "Set E/Mango.png"), ("orange", ["or", "ange"], "easy", "Set E/Orange.png"), ("banana", ["ba", "na", "na"], "medium", "Set E/Banana.png"), ("watermelon", ["wa", "ter", "mel", "on"], "hard", "Set E/Watermelon.png"), ("pizza", ["piz", "za"], "easy", "Set A/Fruit.png"), ("cookie", ["cook", "ie"], "easy", "Set A/Fruit.png"), ("tomato", ["to", "ma", "to"], "medium", "Set A/Fruit.png"), ("potato", ["po", "ta", "to"], "medium", "Set A/Fruit.png"), ("chocolate", ["choc", "o", "late"], "medium", "Set A/Fruit.png")],
        "things_around_us": [("book", ["book"], "easy", "Set F/Book.png"), ("chair", ["chair"], "easy", "Set F/Chair.png"), ("desk", ["desk"], "easy", "Set F/Desk.png"), ("pencil", ["pen", "cil"], "easy", "Set F/Pencil.png"), ("eraser", ["e", "ras", "er"], "medium", "Set F/Eraser.png"), ("wallet", ["wal", "let"], "easy", "Set B/Wallet.png"), ("umbrella", ["um", "brel", "la"], "medium", "Set B/Umbrella.png"), ("robot", ["ro", "bot"], "easy", "Set B/Robot.png"), ("medicine", ["med", "i", "cine"], "medium", "Set A/Medicine.png"), ("rubber band", ["rub", "ber", "band"], "hard", "Set A/RubberBand.png")],
        "nature": [("sun", ["sun"], "easy", "Set A/Branch.png"), ("rain", ["rain"], "easy", "Set A/Branch.png"), ("tree", ["tree"], "easy", "Set A/Branch.png"), ("river", ["riv", "er"], "easy", "Set B/Railway.png"), ("ocean", ["o", "cean"], "easy", "Set D/Fish.png"), ("flower", ["flow", "er"], "easy", "Set A/Branch.png"), ("mountain", ["moun", "tain"], "medium", "Set A/Branch.png"), ("rainbow", ["rain", "bow"], "medium", "Set A/Branch.png"), ("thunder", ["thun", "der"], "medium", "Set A/Branch.png"), ("hurricane", ["hur", "ri", "cane"], "hard", "Set A/Branch.png")],
        "people_and_places": [("teacher", ["teach", "er"], "easy", "Set G/Teacher.png"), ("doctor", ["doc", "tor"], "easy", "Set G/Doctor.png"), ("nurse", ["nurse"], "easy", "Set G/Nurse.png"), ("police", ["po", "lice"], "easy", "Set G/Police.png"), ("firefighter", ["fire", "fight", "er"], "medium", "Set G/FIrefighter.png"), ("school", ["school"], "easy", "Set F/Desk.png"), ("market", ["mar", "ket"], "easy", "Set A/Fruit.png"), ("hospital", ["hos", "pi", "tal"], "medium", "Set G/Doctor.png"), ("library", ["li", "brar", "y"], "medium", "Set F/Book.png"), ("playground", ["play", "ground"], "medium", "Set A/Branch.png")],
    },
}


def word_bank_catalog():
    result = {language: {"sets": [], "words": []} for language in SETS}
    for language, sets in SETS.items():
        for set_key, label in sets:
            result[language]["sets"].append({"id": set_key, "name": label})
            for index, (word, syllables, difficulty, asset) in enumerate(_WORDS[language][set_key], 1):
                result[language]["words"].append({
                    "id": f"{language[:2].lower()}_{set_key}_{index:02d}", "language": language,
                    "set": set_key, "word": word, "syllables": syllables,
                    "syllable_count": len(syllables),
                    "image": f"pabasa_app/images/picture_word/{asset}",
                    "difficulty": difficulty, "active": True,
                })
    return deepcopy(result)


def validate_configuration(payload):
    catalog = word_bank_catalog()
    language = str(payload.get("language") or "")
    set_id = str(payload.get("word_set") or "")
    selected_ids = payload.get("selected_word_ids") or []
    number = payload.get("number_of_words")
    if language not in catalog:
        raise ValueError("Language must be Filipino or English.")
    valid_sets = {item["id"] for item in catalog[language]["sets"]}
    if set_id not in valid_sets:
        raise ValueError("Choose a word set for the selected language.")
    valid_words = {item["id"]: item for item in catalog[language]["words"] if item["set"] == set_id and item["active"]}
    if not selected_ids or any(item_id not in valid_words for item_id in selected_ids):
        raise ValueError("Selected words must belong to the selected language and word set.")
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Selected words must not contain duplicate word IDs.")
    try:
        number = int(number)
    except (TypeError, ValueError):
        raise ValueError("Choose a valid number of words.")
    if number < 1 or number > len(selected_ids):
        raise ValueError("Number of words cannot exceed the selected words.")
    return [valid_words[item_id] for item_id in selected_ids[:number]]


def score_displayed_words(displayed_words, submitted_answers):
    """Resolve the latest answer per word ID and score every displayed word once."""
    displayed_by_id = {}
    for word in displayed_words or []:
        if not isinstance(word, dict):
            continue
        word_id = str(word.get("id") or "").strip()
        if not word_id or word_id in displayed_by_id:
            continue
        displayed_by_id[word_id] = word

    latest_answers = {}
    attempts = []
    for raw_answer in submitted_answers or []:
        if not isinstance(raw_answer, dict):
            continue
        word_id = str(raw_answer.get("word_id") or "").strip()
        if word_id not in displayed_by_id:
            continue
        try:
            selected = int(raw_answer.get("answer"))
        except (TypeError, ValueError):
            selected = None
        try:
            claps = max(0, int(raw_answer.get("claps") or 0))
        except (TypeError, ValueError):
            claps = 0
        attempt = {"word_id": word_id, "answer": selected, "claps": claps}
        attempts.append(attempt)
        latest_answers[word_id] = attempt

    results = []
    for word_id, word in displayed_by_id.items():
        expected = int(word.get("syllable_count") or len(word.get("syllables") or []))
        final_answer = latest_answers.get(word_id)
        selected = final_answer["answer"] if final_answer else None
        results.append({
            "word_id": word_id,
            "word": str(word.get("word") or ""),
            "answer": selected,
            "expected_syllables": expected,
            "claps": final_answer["claps"] if final_answer else 0,
            "is_correct": selected == expected,
        })

    total_items = len(results)
    correct_items = sum(1 for result in results if result["is_correct"])
    accuracy = round((correct_items / total_items) * 100, 2) if total_items else 0
    return {
        "answers": results,
        "attempts": attempts,
        "correct_items": correct_items,
        "items_completed": total_items,
        "accuracy": accuracy,
    }
