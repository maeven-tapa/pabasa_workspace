from django.test import SimpleTestCase

from .clap_count_word_bank import (
    SETS, score_displayed_words, validate_configuration, word_bank_catalog,
)


class ClapCountWordBankTests(SimpleTestCase):
    def test_catalog_has_exactly_five_sets_and_ten_words_per_set(self):
        catalog = word_bank_catalog()
        self.assertEqual(set(catalog), {"Filipino", "English"})
        for language in catalog:
            self.assertEqual(len(catalog[language]["sets"]), 5)
            for set_id, _ in SETS[language]:
                words = [word for word in catalog[language]["words"] if word["set"] == set_id]
                self.assertEqual(len(words), 10)
                self.assertTrue(all(word["syllable_count"] == len(word["syllables"]) for word in words))

    def test_configuration_rejects_cross_language_and_over_limit_selection(self):
        catalog = word_bank_catalog()
        filipino = next(word for word in catalog["Filipino"]["words"] if word["set"] == "mga_hayop")
        english = next(word for word in catalog["English"]["words"] if word["set"] == "animals")
        base = {"language": "Filipino", "word_set": "mga_hayop", "number_of_words": 1}
        with self.assertRaises(ValueError):
            validate_configuration({**base, "selected_word_ids": [english["id"]]})
        with self.assertRaises(ValueError):
            validate_configuration({**base, "selected_word_ids": [filipino["id"]], "number_of_words": 2})

    def test_valid_configuration_returns_authoritative_records(self):
        words = [word for word in word_bank_catalog()["English"]["words"] if word["set"] == "food"][:3]
        result = validate_configuration({"language": "English", "word_set": "food", "selected_word_ids": [word["id"] for word in words], "number_of_words": 3})
        self.assertEqual([word["word"] for word in result], ["apple", "mango", "orange"])

    def test_configuration_applies_number_of_words(self):
        words = [word for word in word_bank_catalog()["English"]["words"] if word["set"] == "food"]
        result = validate_configuration({"language": "English", "word_set": "food", "selected_word_ids": [word["id"] for word in words], "number_of_words": 5})
        self.assertEqual(len(result), 5)

    def test_configuration_rejects_duplicate_word_ids(self):
        word = next(word for word in word_bank_catalog()["English"]["words"] if word["set"] == "food")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_configuration({"language": "English", "word_set": "food", "selected_word_ids": [word["id"], word["id"]], "number_of_words": 2})


class ClapCountScoringTests(SimpleTestCase):
    def setUp(self):
        self.words = [
            {"id": f"word-{index}", "word": f"word {index}", "syllable_count": (index % 4) + 1}
            for index in range(10)
        ]

    def answers_for(self, words, correct=True, **extra):
        return [{"word_id": word["id"], "answer": word["syllable_count"] if correct else 9, **extra} for word in words]

    def test_five_of_ten_is_fifty_percent(self):
        answers = self.answers_for(self.words[:5]) + self.answers_for(self.words[5:], correct=False)
        score = score_displayed_words(self.words, answers)
        self.assertEqual((score["correct_items"], score["items_completed"], score["accuracy"]), (5, 10, 50.0))

    def test_ten_of_ten_is_one_hundred_percent(self):
        score = score_displayed_words(self.words, self.answers_for(self.words))
        self.assertEqual((score["correct_items"], score["accuracy"]), (10, 100.0))

    def test_randomized_answer_order_does_not_change_score(self):
        score = score_displayed_words(self.words, list(reversed(self.answers_for(self.words))))
        self.assertEqual(score["correct_items"], 10)

    def test_only_displayed_subset_is_in_denominator(self):
        displayed = self.words[:5]
        score = score_displayed_words(displayed, self.answers_for(displayed))
        self.assertEqual((score["correct_items"], score["items_completed"], score["accuracy"]), (5, 5, 100.0))

    def test_retry_uses_latest_answer_for_same_word(self):
        answers = [{"word_id": self.words[0]["id"], "answer": 9}, {"word_id": self.words[0]["id"], "answer": self.words[0]["syllable_count"]}] + self.answers_for(self.words[1:])
        score = score_displayed_words(self.words, answers)
        self.assertEqual(score["correct_items"], 10)
        self.assertEqual(len(score["answers"]), 10)

    def test_claps_do_not_affect_correctness(self):
        correct = score_displayed_words(self.words[:1], self.answers_for(self.words[:1], claps=999))
        incorrect = score_displayed_words(self.words[:1], self.answers_for(self.words[:1], correct=False, claps=self.words[0]["syllable_count"]))
        self.assertTrue(correct["answers"][0]["is_correct"])
        self.assertFalse(incorrect["answers"][0]["is_correct"])

    def test_duplicate_submissions_do_not_inflate_denominator(self):
        answers = self.answers_for(self.words) + self.answers_for(self.words)
        score = score_displayed_words(self.words, answers)
        self.assertEqual(score["items_completed"], 10)

    def test_duplicate_displayed_ids_are_safely_deduplicated(self):
        score = score_displayed_words([self.words[0], self.words[0]], self.answers_for(self.words[:1]))
        self.assertEqual(score["items_completed"], 1)

    def test_missing_answer_is_incorrect_without_changing_denominator(self):
        score = score_displayed_words(self.words, self.answers_for(self.words[:9]))
        self.assertEqual((score["correct_items"], score["items_completed"], score["accuracy"]), (9, 10, 90.0))
        self.assertIsNone(score["answers"][-1]["answer"])

    def test_client_correctness_flags_are_ignored(self):
        forced_true = self.answers_for(self.words[:1], correct=False, is_correct=True)
        forced_false = self.answers_for(self.words[1:2], is_correct=False)
        self.assertFalse(score_displayed_words(self.words[:1], forced_true)["answers"][0]["is_correct"])
        self.assertTrue(score_displayed_words(self.words[1:2], forced_false)["answers"][0]["is_correct"])

    def test_randomization_and_retries_can_still_produce_full_score(self):
        randomized = list(reversed(self.words))
        answers = []
        for word in randomized:
            answers.extend([{"word_id": word["id"], "answer": 9}, {"word_id": word["id"], "answer": word["syllable_count"]}])
        score = score_displayed_words(self.words, answers)
        self.assertEqual((score["correct_items"], score["items_completed"], score["accuracy"]), (10, 10, 100.0))
