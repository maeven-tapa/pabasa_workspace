import re

from django import forms

from .models import Material


def parse_practice_items(content, item_type):
    content = (content or "").strip()
    if item_type in {"word", "vowel"}:
        return re.findall(r"\b[\w']+\b", content, flags=re.UNICODE)
    if item_type == "sentence":
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", content) if part.strip()]
    if item_type == "paragraph":
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines
        return [part.strip() for part in re.split(r"\n{2,}", content) if part.strip()]
    return [content] if content else []


def mode_to_item_type(mode):
    mapping = {
        "free": "word",
        "color": "sentence",
        "hunt": "paragraph",
    }
    return mapping.get((mode or "").strip().lower(), "word")


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
        ("English", "English"),
        ("Filipino", "Filipino"),
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

    def get_occupied_levels(self, mode=None, difficulty=None, language=None, material=None):
        selected_mode = mode or self.data.get("mode") or self.initial.get("mode")
        selected_difficulty = difficulty or self.data.get("difficulty_level") or self.initial.get("difficulty_level")
        selected_language = (
            language
            or self.data.get("language")
            or self.initial.get("language")
            or (getattr(material or self.material, "language", "") if (material or self.material) else "")
        )
        selected_language = Material.normalize_language_value(selected_language)
        if not selected_mode or not selected_difficulty:
            return []

        queryset = Material.objects.filter(
            type="practice",
            content_json__mode=selected_mode,
            content_json__difficulty=selected_difficulty,
            language=selected_language,
        )
        material_obj = material or self.material
        if material_obj:
            queryset = queryset.exclude(pk=material_obj.pk)
        occupied_levels = sorted({
            level for level in queryset.values_list("content_json__level", flat=True) if level
        })
        return occupied_levels

    def _expected_item_type(self, mode=None):
        return mode_to_item_type(mode or self.cleaned_data.get("mode"))

    def _parse_content_items(self, content, mode=None):
        return parse_practice_items(content, self._expected_item_type(mode))

    def _validate_content_type(self, content, mode, field_label="content"):
        expected_type = self._expected_item_type(mode)
        items = self._parse_content_items(content, mode)
        if not items:
            if expected_type == "word":
                raise forms.ValidationError("At least one word is required.")
            if expected_type == "sentence":
                raise forms.ValidationError("At least one sentence is required.")
            raise forms.ValidationError("At least one paragraph is required.")
        if expected_type == "word" and any(len(item.split()) != 1 for item in items):
            raise forms.ValidationError("Free Mode only accepts single words.")
        if expected_type == "sentence" and any(not re.search(r"[.!?]$", item) for item in items):
            raise forms.ValidationError("Color Mode only accepts sentences.")
        if expected_type == "paragraph" and any("\n" not in item and len(item.split()) < 2 for item in items):
            raise forms.ValidationError("Hunt Mode only accepts paragraphs.")
        return items

    def clean_content_text(self):
        content = (self.cleaned_data.get("content_text") or "").strip()
        mode = self.cleaned_data.get("mode")
        items = self._validate_content_type(content, mode)
        if mode == "color" and len(items) > self.MAX_ITEMS_PER_CONTENT:
            raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} sentences are allowed for each level in Color Mode.")
        return content

    def practice_items(self):
        content = self.cleaned_data.get("content_text", "")
        return self._parse_content_items(content, self.cleaned_data.get("mode"))

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("mode")
        if "content_text" not in self.errors and mode:
            content = (cleaned_data.get("content_text") or "").strip()
            items = self._parse_content_items(content, mode)
            if mode == "color" and len(items) > self.MAX_ITEMS_PER_CONTENT:
                raise forms.ValidationError(f"Only up to {self.MAX_ITEMS_PER_CONTENT} sentences are allowed for each level in Color Mode.")
        difficulty = cleaned_data.get("difficulty_level")
        level = cleaned_data.get("level")
        if mode and difficulty and level:
            duplicate_query = Material.objects.filter(
                type="practice",
                content_json__mode=mode,
                content_json__difficulty=difficulty,
                content_json__level=level,
                language=Material.normalize_language_value(cleaned_data.get("language")),
            )
            if self.material:
                duplicate_query = duplicate_query.exclude(pk=self.material.pk)
            if duplicate_query.exists():
                raise forms.ValidationError("A Practice Content already exists for the selected Mode, Difficulty, and Level.")
        return cleaned_data
