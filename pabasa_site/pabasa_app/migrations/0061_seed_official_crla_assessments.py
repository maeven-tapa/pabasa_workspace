from django.db import migrations


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
            }
        ],
    },
}


def seed_official_crla_assessments(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")
    User = apps.get_model("pabasa_app", "User")
    admin_user = User.objects.filter(role="admin", is_archived=False).order_by("id").first()

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
        Material.objects.update_or_create(
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


class Migration(migrations.Migration):

    dependencies = [
        ("pabasa_app", "0060_official_reading_override_security_lockout"),
    ]

    operations = [
        migrations.RunPython(seed_official_crla_assessments, migrations.RunPython.noop),
    ]
