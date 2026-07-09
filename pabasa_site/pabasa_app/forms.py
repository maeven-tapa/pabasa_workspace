import re

from django import forms

from .models import Material


def parse_practice_items(content, item_type):
    content = (content or "").strip()
    if item_type == "word":
        return re.findall(r"\b[\w']+\b", content, flags=re.UNICODE)
    if item_type == "sentence":
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", content) if part.strip()]
    if item_type == "paragraph":
        return [part.strip() for part in re.split(r"\n{2,}", content) if part.strip()]
    return [content] if content else []


class AdminPracticeMaterialForm(forms.Form):
    MAX_ITEMS_PER_CONTENT = 5

    MODE_CHOICES = [
        ("free", "Free Mode"),
        ("color", "Color Mode"),
        ("hunt", "Hunt Mode"),
    ]
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]
    LEVEL_CHOICES = [
        ("level_1", "Level 1"),
        ("level_2", "Level 2"),
        ("level_3", "Level 3"),
        ("level_4", "Level 4"),
        ("level_5", "Level 5"),
    ]
    STATUS_CHOICES = [
        ("published", "Published"),
        ("draft", "Draft"),
    ]
    LANGUAGE_CHOICES = [
        ("Filipino", "Filipino"),
        ("English", "English"),
    ]

    mode = forms.ChoiceField(choices=MODE_CHOICES)
    difficulty_level = forms.ChoiceField(choices=DIFFICULTY_CHOICES)
    level = forms.ChoiceField(choices=LEVEL_CHOICES)
    status = forms.ChoiceField(choices=STATUS_CHOICES)
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES, required=True)
    content_text = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.material = kwargs.pop("material", None)
        super().__init__(*args, **kwargs)

    def get_occupied_levels(self, mode=None, difficulty=None, material=None):
        selected_mode = mode or self.data.get("mode") or self.initial.get("mode")
        selected_difficulty = difficulty or self.data.get("difficulty_level") or self.initial.get("difficulty_level")
        if not selected_mode or not selected_difficulty:
            return []

        queryset = Material.objects.filter(
            type="practice",
            content_json__mode=selected_mode,
            content_json__difficulty=selected_difficulty,
        )
        material_obj = material or self.material
        if material_obj:
            queryset = queryset.exclude(pk=material_obj.pk)
        occupied_levels = sorted({
            level for level in queryset.values_list("content_json__level", flat=True) if level
        })
        return occupied_levels

    def clean_content_text(self):
        content = (self.cleaned_data.get("content_text") or "").strip()
        difficulty = self.cleaned_data.get("difficulty_level")
        mode = self.cleaned_data.get("mode")
        if difficulty in {"easy", "medium"}:
            if not content:
                raise forms.ValidationError("At least one item is required.")
            item_count = len(parse_practice_items(content, "word"))
            if mode == "color" and item_count > self.MAX_ITEMS_PER_CONTENT:
                raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} items are allowed for each difficulty and level in Color Mode.")
        elif difficulty == "hard":
            if not [line.strip() for line in content.splitlines() if line.strip()]:
                raise forms.ValidationError("At least one sentence is required.")
            sentence_count = len([line.strip() for line in content.splitlines() if line.strip()])
            if mode == "color" and sentence_count > self.MAX_ITEMS_PER_CONTENT:
                raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} sentences are allowed for each difficulty and level in Color Mode.")
        return content

    def practice_items(self):
        content = self.cleaned_data.get("content_text", "")
        item_type = "sentence" if self.cleaned_data.get("difficulty_level") == "hard" else "word"
        return parse_practice_items(content, item_type)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("difficulty_level") in {"easy", "medium"} and not self.practice_items():
            raise forms.ValidationError("At least one item is required.")
        if cleaned_data.get("difficulty_level") == "hard" and not self.practice_items():
            raise forms.ValidationError("At least one sentence is required.")
        mode = cleaned_data.get("mode")
        if mode == "color" and cleaned_data.get("difficulty_level") in {"easy", "medium"} and len(self.practice_items()) > self.MAX_ITEMS_PER_CONTENT:
            raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} items are allowed for each difficulty and level in Color Mode.")
        if mode == "color" and cleaned_data.get("difficulty_level") == "hard" and len(self.practice_items()) > self.MAX_ITEMS_PER_CONTENT:
            raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} sentences are allowed for each difficulty and level in Color Mode.")
        difficulty = cleaned_data.get("difficulty_level")
        level = cleaned_data.get("level")
        if mode and difficulty and level:
            duplicate_query = Material.objects.filter(
                type="practice",
                content_json__mode=mode,
                content_json__difficulty=difficulty,
                content_json__level=level,
            )
            if self.material:
                duplicate_query = duplicate_query.exclude(pk=self.material.pk)
            if duplicate_query.exists():
                raise forms.ValidationError("A Practice Content already exists for the selected Mode, Difficulty, and Level.")
        return cleaned_data
