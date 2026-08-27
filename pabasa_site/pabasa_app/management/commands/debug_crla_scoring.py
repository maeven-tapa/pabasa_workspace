"""Read-only verification of the CRLA scoring payload used by assessments."""

from django.core.management.base import BaseCommand

from pabasa_app.scoring import (
    build_assessment_score_payload,
    crla_part1_classification,
    crla_part1_total,
    crla_part2_profile,
    crla_task1_next_task,
)


class Command(BaseCommand):
    help = "Print deterministic, read-only CRLA scoring verification cases."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failed = False

    def line(self, value=""):
        self.stdout.write(value)

    def verify(self, name, expected, actual):
        passed = expected == actual
        self.failed = self.failed or not passed
        self.line(f"[{'PASS' if passed else 'FAIL'}] {name}: {expected} -> {actual}")

    def handle(self, *args, **options):
        self.line("=" * 60)
        self.line("CRLA SCORING DEBUG")
        self.line("=" * 60)
        self.line("All cases use in-memory dictionaries only; no database writes occur.")
        self.line("")

        task1_cases = ((0, "Task 2L / Rhymes"), (1, "Task 2L / Rhymes"),
                       (6, "Task 2L / Rhymes"), (7, "Task 2H / Sentences"),
                       (8, "Task 2H / Sentences"), (9, "Task 2H / Sentences"),
                       (10, "Task 2H / Sentences"))
        for correct, expected_task in task1_cases:
            payload = build_assessment_score_payload({
                "assessment_type": "word", "correct_words": correct,
                "target_word_count": 10, "duration_seconds": 60,
            })
            actual_task = crla_task1_next_task(payload["crla_task_score"])
            self.line(f"Task 1 total items: 10")
            self.line(f"Task 1 correct: {correct}")
            self.line(f"Task 1 score: {payload['crla_task_score']}")
            self.line(f"selected next task: {actual_task}")
            self.verify(f"Task 1: {correct} correct", expected_task, actual_task)

        self.line("\n" + "-" * 60)
        self.line("PART 1 CLASSIFICATION BOUNDARIES")
        self.line("-" * 60)
        for score, expected in ((10, "Full Refresher"), (11, "Moderate Refresher"),
                (16, "Moderate Refresher"), (17, "Light Refresher"),
                (26, "Light Refresher"), (27, "Grade Ready"), (30, "Grade Ready")):
            payload = build_assessment_score_payload({"assessment_type": "sentence", "part1_total_score": score})
            actual = payload["crla_classification"]
            self.line(f"Task 1 Score: n/a; Task 2L Score: n/a; Task 2H Score: n/a")
            self.line(f"Part 1 Total: {payload['part1_total_score']}; Part 1 Maximum: 30")
            self.line(f"Part 1 Classification: {actual}")
            self.verify(str(score), expected, actual)

        self.line("\nApplicable-task total checks")
        for task1, task2l, task2h in ((6, 5, None), (7, None, 8)):
            total = crla_part1_total(task1, task2l, task2h)
            payload = build_assessment_score_payload({"assessment_type": "sentence", "part1_total_score": total})
            self.line(f"Task 1 Score: {task1}")
            self.line(f"Task 2L Score: {task2l if task2l is not None else 'not applicable'}")
            self.line(f"Task 2H Score: {task2h if task2h is not None else 'not applicable'}")
            self.line(f"Part 1 Total: {total}")
            self.line("Part 1 Maximum: 30")
            self.line(f"Part 1 Classification: {payload['crla_classification']}")
            self.verify(f"applicable total for Task 1 = {task1}", total, payload["final_score"])

        self.line("\n" + "-" * 60)
        self.line("PART 2")
        self.line("-" * 60)
        # Deterministic case: 80 story words, 60 read, 3 miscues, 90 seconds, 3/5 comprehension.
        profile = crla_part2_profile(80, 60, 3, 90, 3)
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph", "total_story_words": 80, "target_word_count": 80,
            "words_read": 60, "correct_words": 57, "incorrect_words": 3, "miscues": 3,
            "duration_seconds": 90, "correct_answers": 3,
        })
        labels = ("High Emerging", "Developing", "Transitioning", "Grade Level")
        self.line(f"Total Words: {profile['total_story_words']}")
        self.line(f"Words Read: {profile['words_read']}")
        self.line(f"Miscues: {profile['miscues']}")
        self.line(f"Duration: {profile['duration_seconds']} seconds")
        self.line(f"WPM: {profile['wpm']}")
        self.line(f"Correct Word %: {profile['correct_word_percent']}")
        self.line(f"Comprehension Correct: {profile['comprehension_correct']}")
        self.line(f"Reading Band: {profile['reading_band']} ({labels[profile['reading_band']]})")
        self.line(f"Comprehension Band: {profile['comprehension_band']} ({labels[profile['comprehension_band']]})")
        self.line(f"Final Part 2 Band: {profile['final_part2_band']}")
        self.line(f"Final Part 2 Classification: {payload['crla_classification']}")
        self.verify("Part 2 payload classification", profile["classification"], payload["crla_classification"])

        self.line("\n" + "-" * 60)
        self.line("LEGACY SCORING CHECK")
        self.line("-" * 60)
        legacy = build_assessment_score_payload({"assessment_type": "word", "correct_words": 6, "target_word_count": 10})
        multiplier = legacy.get("osps_multiplier")
        self.line(f"OSPS multiplier: {'NONE' if multiplier == 1.0 else multiplier}")
        self.line("70/15/10/5 weighting: NOT USED" if legacy["final_score"] == legacy["crla_task_score"] else "70/15/10/5 weighting: DETECTED")
        self.line("final_score = raw CRLA task or supplied Part 1 total; source = overall_raw_score; official CRLA meaning = verified only when Part 1 total is supplied.")
        self.line("total_score = alias of final_score; source = final_score; official CRLA meaning = same conditional meaning.")
        self.line("overall_raw_score = raw CRLA task score or supplied Part 1 total; it is not a weighted percentage.")
        self.verify("OSPS multiplier", 1.0, multiplier)
        self.verify("no weighted score", legacy["crla_task_score"], legacy["final_score"])

        self.line("\n" + "=" * 60)
        self.line(f"RESULT: {'FAIL' if self.failed else 'PASS'}")
        self.line("=" * 60)
        if self.failed:
            raise SystemExit(1)
