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
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]
    STATUS_CHOICES = [
        ("published", "Published"),
        ("draft", "Draft"),
    ]

    title = forms.CharField(max_length=150)
    difficulty_level = forms.ChoiceField(choices=DIFFICULTY_CHOICES)
    item_type = forms.ChoiceField(choices=Material.ITEM_TYPE_CHOICES)
    status = forms.ChoiceField(choices=STATUS_CHOICES)
    prompt_text = forms.CharField(required=False, widget=forms.Textarea)
    content_text = forms.CharField(widget=forms.Textarea)

    def clean_content_text(self):
        content = self.cleaned_data["content_text"].strip()
        if not content:
            raise forms.ValidationError("Content is required.")
        return content

    def practice_items(self):
        content = self.cleaned_data.get("content_text", "")
        item_type = self.cleaned_data.get("item_type")
        return parse_practice_items(content, item_type)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("content_text") and cleaned_data.get("item_type") and not self.practice_items():
            raise forms.ValidationError("No practice items could be created from the content.")
        return cleaned_data
