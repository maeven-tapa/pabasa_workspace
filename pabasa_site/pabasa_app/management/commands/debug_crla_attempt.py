"""Read-only inspection of a persisted CRLA assessment attempt."""

import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from pabasa_app.models import Assessment, User
from pabasa_app.scoring import (
    build_assessment_score_payload,
    crla_part1_classification,
    crla_part1_total,
    crla_part2_profile,
    crla_task1_next_task,
)


def _shown(value):
    return "NOT AVAILABLE IN DATABASE" if value in (None, "") else str(value)


def _match(command, label, database_value, recalculated_value):
    match = database_value == recalculated_value if database_value not in (None, "") else None
    command.stdout.write(f"{label}")
    command.stdout.write(f"  DATABASE VALUE: {_shown(database_value)}")
    command.stdout.write(f"  RECALCULATED VALUE: {_shown(recalculated_value)}")
    command.stdout.write(f"  MATCH: {'YES' if match is True else 'NO' if match is False else 'N/A (not persisted)'}")


class Command(BaseCommand):
    help = "Read and recalculate a saved CRLA attempt without changing database state."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--student", help="Student database ID or custom ID; requires --latest.")
        group.add_argument("--assessment", type=int, help="Persisted Assessment result-row ID.")
        parser.add_argument("--latest", action="store_true", help="Select the latest completed CRLA result for --student.")

    def handle(self, *args, **options):
        if options["student"] and not options["latest"]:
            raise CommandError("Use --student <student_id> --latest to avoid choosing an attempt implicitly.")

        if options["assessment"]:
            attempt = Assessment.objects.select_related("student", "material", "source_assessment").filter(
                pk=options["assessment"]
            ).first()
            if not attempt:
                raise CommandError("No Assessment result row exists with that ID.")
        else:
            student_key = str(options["student"]).strip()
            if student_key.isdigit():
                student = User.objects.filter(
                    Q(pk=int(student_key)) | Q(custom_id=student_key), role="student"
                ).first()
            else:
                student = User.objects.filter(custom_id=student_key, role="student").first()
            if not student:
                raise CommandError("No student matches that database ID or custom ID.")
            attempt = self._crla_attempts().filter(student=student, attempt_status="completed").order_by(
                "-completed_at", "-updated_at", "-created_at", "-id"
            ).first()
            if not attempt:
                raise CommandError("No completed CRLA Assessment result row exists for that student.")

        if not self._is_crla(attempt):
            raise CommandError("The selected Assessment row is not an official/CRLA attempt.")
        self._print_attempt(attempt)

    @staticmethod
    def _crla_attempts():
        return Assessment.objects.select_related("student", "material", "source_assessment").filter(
            Q(material__assessment_kind="crla")
            | Q(material__is_official_reading=True)
            | Q(is_system_owned=True)
            | Q(system_assessment_key__icontains="crla")
        )

    @staticmethod
    def _is_crla(attempt):
        material = attempt.material
        return bool(
            getattr(material, "assessment_kind", "") == "crla"
            or getattr(material, "is_official_reading", False)
            or attempt.is_system_owned
            or "crla" in str(attempt.system_assessment_key or "").lower()
        )

    @staticmethod
    def _state_for(attempt):
        """Return the attempt-bound CRLA record; preference state is legacy fallback."""
        if isinstance(attempt.crla_score_data, dict) and attempt.crla_score_data:
            return attempt.crla_score_data, "Assessment.crla_score_data"
        preference = getattr(attempt.student, "preference", None) or {}
        state = preference.get("reading_assessment_state") if isinstance(preference, dict) else None
        if not isinstance(state, dict):
            return {}, "NOT AVAILABLE IN DATABASE"
        material_id = str(attempt.material_id or "")
        states = state.get("crla_result_states")
        if material_id and isinstance(states, dict) and isinstance(states.get(material_id), dict):
            return states[material_id], "student.preference.reading_assessment_state.crla_result_states"
        end_state = state.get("student_end_assessment_state")
        if isinstance(end_state, dict) and str(end_state.get("material_id", "")).split(":")[-1] == material_id:
            return end_state, "student.preference.reading_assessment_state.student_end_assessment_state"
        return {}, "NOT AVAILABLE FOR THIS ATTEMPT"

    def _print_attempt(self, attempt):
        material = attempt.material
        state, state_source = self._state_for(attempt)
        assessment_type = str(attempt.assessment_type or getattr(material, "item_type", "") or "").lower()
        phase = attempt.system_assessment_phase or getattr(material, "system_assessment_phase", "") or "NOT AVAILABLE"
        self.stdout.write("=" * 60)
        self.stdout.write("CRLA REAL ATTEMPT DEBUG")
        self.stdout.write("=" * 60)
        self.stdout.write("READ-ONLY: this command performs queries only; it does not save or update records.")
        self.stdout.write(f"Student: {attempt.student} (id={attempt.student_id})")
        self.stdout.write(f"Assessment result row: {attempt.id} ({attempt.code})")
        self.stdout.write(f"Phase: {str(phase).upper()}")
        self.stdout.write(f"Material: {_shown(getattr(material, 'title', None))} (id={attempt.material_id})")
        self.stdout.write(f"Completed: {_shown(attempt.completed_at)}")
        self.stdout.write(f"Attempt-row type: {_shown(assessment_type)}")
        self.stdout.write(f"Cross-task state source: {state_source}")

        task1 = state.get("task1_score") if state.get("task1_score") is not None else state.get("task1_correct_words")
        if task1 is None and assessment_type == "word":
            task1 = attempt.word_count if attempt.word_count is not None else attempt.correct_items
        task2l = state.get("task2_score") if "l" in str(state.get("task2_type") or "").lower() else state.get("task2_rhymes_score")
        task2h = state.get("task2_score") if "h" in str(state.get("task2_type") or "").lower() else state.get("task2_sentences_score")
        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("PART 1 — WORD RECOGNITION")
        self.stdout.write("-" * 60)
        self.stdout.write(f"Total Task 1 Words: {_shown(state.get('task1_total_words') or 10)}")
        self.stdout.write(f"Correct Words: {_shown(task1)}")
        self.stdout.write(f"Task 1 Score: {_shown(task1)}")
        if task1 is None:
            self.stdout.write("Branch: NOT AVAILABLE IN DATABASE")
        else:
            self.stdout.write(f"Branch: {task1} → {crla_task1_next_task(task1)}")

        self.stdout.write("\nTASK 2")
        if task2l is not None:
            self.stdout.write(f"Task 2L / Rhymes score: {task2l}")
        elif task2h is not None:
            self.stdout.write(f"Task 2H / Sentences score: {task2h}")
        else:
            self.stdout.write("Task 2 response/aggregate score: NOT AVAILABLE FOR THIS ATTEMPT")

        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("PART 1 TOTAL")
        self.stdout.write("-" * 60)
        stored_part1 = state.get("part1_total_score")
        if task1 is not None and (task2l is not None or task2h is not None) and not (task2l is not None and task2h is not None):
            recalculated_part1 = crla_part1_total(task1, task2l, task2h)
            applicable_name = "Task 2L" if task2l is not None else "Task 2H"
            applicable_score = task2l if task2l is not None else task2h
            self.stdout.write(f"Calculation: {task1} + {applicable_score} = {recalculated_part1}")
            self.stdout.write(f"Part 1 Score: {recalculated_part1} / 30")
            self.stdout.write(f"Part 1 Classification: {crla_part1_classification(recalculated_part1)}")
            self.stdout.write(f"Applicable Task 2: {applicable_name}")
        else:
            recalculated_part1 = None
            self.stdout.write("Calculation: NOT AVAILABLE — both Task 1 and exactly one Task 2 aggregate are required.")
        _match(self, "Part 1 total", stored_part1, recalculated_part1)

        self._print_part2(attempt, material, state)
        self._print_stored_values(attempt, state, assessment_type)

    def _print_part2(self, attempt, material, state):
        content = getattr(material, "content_text", "") or getattr(material, "prompt_text", "") or ""
        material_word_count = len(re.findall(r"\b[\w'-]+\b", content)) if content else None
        total_words = state.get("story_total_words") if state.get("story_total_words") is not None else state.get("total_story_words")
        words_read = state.get("words_read") if state.get("words_read") is not None else state.get("total_words_read")
        miscues = state.get("miscues")
        duration = state.get("duration_seconds", attempt.duration_seconds)
        answers = state.get("comprehension_correct") if state.get("comprehension_correct") is not None else state.get("correct_answers")
        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("PART 2 — READING FLUENCY AND COMPREHENSION")
        self.stdout.write("-" * 60)
        self.stdout.write(f"Story: {_shown(getattr(material, 'title', None))}")
        self.stdout.write(f"Total Story Words: {_shown(total_words)}" + (f" (material text count: {material_word_count})" if material_word_count is not None else ""))
        self.stdout.write(f"Words Read: {_shown(words_read)}")
        self.stdout.write(f"Miscues: {_shown(miscues)}")
        self.stdout.write(f"Duration: {_shown(duration)}")
        self.stdout.write(f"Total Questions: {_shown(state.get('comprehension_total') or state.get('total_questions'))}")
        self.stdout.write(f"Correct Answers: {_shown(answers)}")
        required = (total_words, words_read, miscues, duration, answers)
        if any(value in (None, "") for value in required):
            self.stdout.write("Recalculation: NOT AVAILABLE — required Part 2 values were not persisted for this attempt.")
            return
        profile = crla_part2_profile(total_words, words_read, miscues, duration, answers)
        payload = build_assessment_score_payload({
            "assessment_type": "paragraph", "total_story_words": total_words, "words_read": words_read,
            "miscues": miscues, "duration_seconds": duration, "correct_answers": answers,
        })
        self.stdout.write(f"WPM: {profile['wpm']}")
        self.stdout.write(f"Passage Accuracy: {_shown(profile['passage_accuracy_percent'])}")
        self.stdout.write(f"Reading Band: {profile['reading_band']}")
        self.stdout.write(f"Comprehension Band: {profile['comprehension_band']}")
        self.stdout.write(f"Final Part 2 Band: {profile['final_part2_band']}")
        _match(self, "Final CRLA Classification", attempt.crla_classification, profile["classification"])

    def _print_stored_values(self, attempt, state, assessment_type):
        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("STORED DATABASE VALUES")
        self.stdout.write("-" * 60)
        fields = {
            "part1_total_score": state.get("part1_total_score"),
            "crla_task_score": "NOT A PERSISTED ASSESSMENT COLUMN",
            "final_score": "NOT A PERSISTED ASSESSMENT COLUMN",
            "total_score": attempt.total_score,
            "crla_classification": attempt.crla_classification,
            "accuracy": attempt.accuracy,
            "wpm": attempt.wpm,
            "duration_seconds": attempt.duration_seconds,
            "fluency_score": attempt.fluency_score,
            "pronunciation_score": attempt.pronunciation_score,
            "time_score": attempt.time_score,
        }
        recalculated = build_assessment_score_payload({
            "assessment_type": assessment_type, "correct_words": attempt.word_count,
            "correct_items": attempt.correct_items, "items_completed": attempt.items_completed,
            "duration_seconds": attempt.duration_seconds,
        })
        for name, value in fields.items():
            recalc = recalculated.get(name) if name in recalculated else None
            _match(self, name, value, recalc)
        self.stdout.write("Word-level responses: NOT AVAILABLE IN DATABASE (the Assessment row stores aggregates only).")
        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("LEGACY SCORING CHECK")
        self.stdout.write("-" * 60)
        self.stdout.write("OSPS multiplier: NONE" if recalculated.get("osps_multiplier") == 1.0 else f"OSPS multiplier: {recalculated.get('osps_multiplier')}")
        self.stdout.write("70/15/10/5 weighted score: NOT USED" if recalculated.get("final_score") == recalculated.get("overall_raw_score") else "70/15/10/5 weighted score: DETECTED")
