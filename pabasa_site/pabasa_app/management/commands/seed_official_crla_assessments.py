from django.core.management.base import BaseCommand
from django.db import transaction

from pabasa_app.models import Material, User


OFFICIAL_CRLA_CONTENT = {
    "bosy_crla_pretest": {
        "code": "CRLA-BOSY",
        "title": "Beginning of School Year (BoSY) CRLA Pre-Test",
        "period": "bosy",
        "phase": "pretest",
        "words": [
            "Binti", "Pito", "Tubig", "Pagod", "Kanta",
            "Regalo", "Butiki", "Halaman", "Malapot", "Gagamba",
        ],
        "sentences": [
            "Naglalaba si Tatay sa palanggana.",
            "Magpapalit ako ng kamiseta mamaya.",
            "Nilinis nila ang agiw rito.",
            "Bumili kami ng bagong suklay.",
        ],
        "passages": [
            {
                "title": "Isang Kakaibang Araw",
                "content": "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!",
            },
            {
                "title": "Ang Pagong at ang Kuneho",
                "content": "\"Ako ang pinakamabilis tumakbo,\" sabi ni Kuneho. \"Wala nang bibilis pa sa akin!\"\n\n\"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo,\" sabi ni Pagong. \"Hinahamon kita sa isang paligsahan.\"\n\n\"Hindi mo ako matatalo!\" sabi ni Kuneho. \"Dahil mas mabilis akong tumakbo!\"\n\n\"Malalaman natin 'yan bukas ng umaga,\" sabi naman ni Pagong.\n\n\"Kapana-panabik ito!\" sabi ni Buwaya.\n\n\"Kawawa naman si Pagong kasi ang bagal niyang gumalaw,\" sabi naman ni Elepante.\n\n\"Kahit mabagal siya ay hindi naman siya tumitigil,\" sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.",
            }
        ],
    },
    "eosy_crla_posttest": {
        "code": "CRLA-EOSY",
        "title": "End of School Year (EoSY) CRLA Post-Test",
        "period": "eosy",
        "phase": "posttest",
        "words": [
            "Binti", "Pito", "Tubig", "Pagod", "Kanta",
            "Regalo", "Butiki", "Halaman", "Malapot", "Gagamba",
        ],
        "sentences": [
            "Naglalaba si Tatay sa palanggana.",
            "Magpapalit ako ng kamiseta mamaya.",
            "Nilinis nila ang agiw rito.",
            "Bumili kami ng bagong suklay.",
        ],
        "passages": [
            {
                "title": "Ang Pagong at ang Kuneho",
                "content": "\"Ako ang pinakamabilis tumakbo,\" sabi ni Kuneho. \"Wala nang bibilis pa sa akin!\"\n\n\"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo,\" sabi ni Pagong. \"Hinahamon kita sa isang paligsahan.\"\n\n\"Hindi mo ako matatalo!\" sabi ni Kuneho. \"Dahil mas mabilis akong tumakbo!\"\n\n\"Malalaman natin 'yan bukas ng umaga,\" sabi naman ni Pagong.\n\n\"Kapana-panabik ito!\" sabi ni Buwaya.\n\n\"Kawawa naman si Pagong kasi ang bagal niyang gumalaw,\" sabi naman ni Elepante.\n\n\"Kahit mabagal siya ay hindi naman siya tumitigil,\" sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.",
            },
            {
                "title": "Isang Kakaibang Araw",
                "content": "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!",
            }
        ],
    },
}

EXPECTED_CRLA_STRUCTURE = {
    "bosy_crla_pretest": {
        "min_passages": 1,
        "min_words": 1,
        "min_sentences": 1,
    },
    "eosy_crla_posttest": {
        "min_passages": 1,
        "min_words": 1,
        "min_sentences": 1,
    },
}


def validate_official_crla_payloads():
    warnings = []
    for key, payload in OFFICIAL_CRLA_CONTENT.items():
        expected = EXPECTED_CRLA_STRUCTURE.get(key, {})
        passages = payload.get("passages") or []
        words = payload.get("words") or []
        sentences = payload.get("sentences") or []
        period = str(payload.get("period") or "").strip().lower()
        phase = str(payload.get("phase") or "").strip().lower()
        label = f"{key} ({period}:{phase})"

        if not passages:
            warnings.append(f"{label} is incomplete: no passages are loaded.")
        elif len(passages) < int(expected.get("min_passages", 1)):
            warnings.append(
                f"{label} is incomplete: expected at least {expected.get('min_passages', 1)} passage(s), loaded {len(passages)}."
            )

        if len(words) < int(expected.get("min_words", 1)):
            warnings.append(
                f"{label} is incomplete: expected at least {expected.get('min_words', 1)} word item(s), loaded {len(words)}."
            )

        if len(sentences) < int(expected.get("min_sentences", 1)):
            warnings.append(
                f"{label} is incomplete: expected at least {expected.get('min_sentences', 1)} sentence item(s), loaded {len(sentences)}."
            )

        total_items = len(words) + len(sentences) + len(passages)
        if total_items <= 0:
            warnings.append(f"{label} is incomplete: no official assessment items were loaded.")

        if key == "bosy_crla_pretest":
            expected_titles = {"Isang Kakaibang Araw", "Ang Pagong at ang Kuneho"}
            actual_titles = {
                str(p.get("title") or "").strip()
                for p in passages
                if isinstance(p, dict) and str(p.get("title") or "").strip()
            }
            missing_titles = sorted(expected_titles - actual_titles)
            if missing_titles:
                warnings.append(
                    f"{label} is missing expected passage title(s): {', '.join(missing_titles)}. Current passage count: {len(passages)}."
                )

    return warnings


class Command(BaseCommand):
    help = "Seed the two official embedded CRLA assessments."

    def _resolve_admin_user(self):
        return User.objects.filter(role="admin", is_archived=False).order_by("id").first()

    @transaction.atomic
    def handle(self, *args, **options):
        warnings = validate_official_crla_payloads()
        for warning in warnings:
            self.stdout.write(self.style.WARNING(warning))

        admin_user = self._resolve_admin_user()
        created = 0
        updated = 0
        for key, payload in OFFICIAL_CRLA_CONTENT.items():
            ordered_items = (
                [{"type": "word", "text": word} for word in payload["words"]]
                + [{"type": "sentence", "text": sentence} for sentence in payload["sentences"]]
                + [{"type": "paragraph", "text": passage["content"], "title": passage["title"]} for passage in payload["passages"]]
            )
            content_json = {
                "assessment_key": key,
                "language": "Filipino",
                "words": payload["words"],
                "sentences": payload["sentences"],
                "passages": payload["passages"],
                "items": ordered_items,
            }
            obj, was_created = Material.objects.update_or_create(
                system_assessment_key=key,
                defaults={
                    "is_system_owned": True,
                    "is_official_reading": True,
                    "system_assessment_period": payload["period"],
                    "system_assessment_phase": payload["phase"],
                    "teacher": admin_user,
                    "section": None,
                    "code": payload["code"],
                    "title": payload["title"],
                    "item_type": "paragraph",
                    "prompt_text": payload["title"],
                    "content_text": "\n".join([
                        *payload["words"],
                        *payload["sentences"],
                        *[p["content"] for p in payload["passages"]],
                    ]),
                    "content_json": content_json,
                    "assessment_set": "crla",
                    "assessment_kind": "crla",
                    "language": "Filipino",
                    "type": "assessment",
                    "source_type": "shared",
                    "status": "published",
                    "student_access": True,
                    "is_active": True,
                },
            )
            self.stdout.write(
                f"CRLA payload ready: {key} period={payload['period']} phase={payload['phase']} items={len(ordered_items)} passages={len(payload['passages'])}"
            )
            obj.is_system_owned = True
            obj.is_official_reading = True
            obj.teacher = admin_user
            obj.section = None
            obj.assessment_set = "crla"
            obj.assessment_kind = "crla"
            obj.system_assessment_period = payload["period"]
            obj.system_assessment_phase = payload["phase"]
            obj.type = "assessment"
            obj.source_type = "shared"
            obj.status = "published"
            obj.student_access = True
            obj.is_active = True
            obj.save()
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f"Official CRLA assessments seeded: {created} created, {updated} updated."))
