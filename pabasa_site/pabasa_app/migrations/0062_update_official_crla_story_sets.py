from django.db import migrations


def update_official_crla_story_sets(apps, schema_editor):
    Material = apps.get_model("pabasa_app", "Material")

    bosy = Material.objects.filter(system_assessment_key="bosy_crla_pretest").first()
    if bosy:
        bosy.content_json = {
            "assessment_key": "bosy_crla_pretest",
            "language": "Filipino",
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
                },
            ],
            "story_qas": [
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Sino ang nagmamaneho ng jeepney?",
                    "answer": "Si Tatay.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang suot ng taong sumakay na bukod-tangi?",
                    "answer": "Makulay at maluwang na damit.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Anong kulay ang malaking sapatos niya?",
                    "answer": "Pula.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang kulay ng kaniyang ilong?",
                    "answer": "Pula.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ilang bola ang inilabas niya mula sa kaniyang bulsa?",
                    "answer": "Limang bola.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang ginawa ng mga tao nang saluhin niya ang mga bola?",
                    "answer": "Napalakpak silang lahat.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing siya ang pinakamabilis tumakbo?",
                    "answer": "Si Kuneho.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang humamon kay Kuneho sa isang paligsahan?",
                    "answer": "Si Pagong.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Kailan sinabi ni Pagong na gaganapin ang paligsahan?",
                    "answer": "Bukas ng umaga.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing kapana-panabik ang paligsahan?",
                    "answer": "Si Buwaya.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing kawawa si Pagong dahil mabagal siyang gumalaw?",
                    "answer": "Si Elepante.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Ano ang sinabi ni Unggoy tungkol kay Pagong?",
                    "answer": "Kahit mabagal siya ay hindi naman siya tumitigil.",
                },
            ],
            "items": [
                {"type": "word", "text": word}
                for word in [
                    "Binti", "Pito", "Tubig", "Pagod", "Kanta",
                    "Regalo", "Butiki", "Halaman", "Malapot", "Gagamba",
                ]
            ] + [
                {"type": "sentence", "text": sentence}
                for sentence in [
                    "Naglalaba si Tatay sa palanggana.",
                    "Magpapalit ako ng kamiseta mamaya.",
                    "Nilinis nila ang agiw rito.",
                    "Bumili kami ng bagong suklay.",
                ]
            ] + [
                {"type": "paragraph", "text": passage["content"], "title": passage["title"]}
                for passage in [
                    {
                        "title": "Isang Kakaibang Araw",
                        "content": "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!",
                    },
                    {
                        "title": "Ang Pagong at ang Kuneho",
                        "content": "\"Ako ang pinakamabilis tumakbo,\" sabi ni Kuneho. \"Wala nang bibilis pa sa akin!\"\n\n\"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo,\" sabi ni Pagong. \"Hinahamon kita sa isang paligsahan.\"\n\n\"Hindi mo ako matatalo!\" sabi ni Kuneho. \"Dahil mas mabilis akong tumakbo!\"\n\n\"Malalaman natin 'yan bukas ng umaga,\" sabi naman ni Pagong.\n\n\"Kapana-panabik ito!\" sabi ni Buwaya.\n\n\"Kawawa naman si Pagong kasi ang bagal niyang gumalaw,\" sabi naman ni Elepante.\n\n\"Kahit mabagal siya ay hindi naman siya tumitigil,\" sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.",
                    },
                ]
            ],
            "is_system_owned": True,
            "is_official_reading": True,
            "system_assessment_period": "bosy",
            "system_assessment_phase": "pretest",
            "assessment_set": "crla",
            "assessment_kind": "crla",
            "language": "Filipino",
            "type": "assessment",
            "source_type": "shared",
            "status": "published",
            "student_access": True,
            "is_active": True,
        }
        bosy.save()

    eosy = Material.objects.filter(system_assessment_key="eosy_crla_posttest").first()
    if eosy:
        eosy.content_json = {
            "assessment_key": "eosy_crla_posttest",
            "language": "Filipino",
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
                },
            ],
            "story_qas": [
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing siya ang pinakamabilis tumakbo?",
                    "answer": "Si Kuneho.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang humamon kay Kuneho sa isang paligsahan?",
                    "answer": "Si Pagong.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Kailan sinabi ni Pagong na gaganapin ang paligsahan?",
                    "answer": "Bukas ng umaga.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing kapana-panabik ang paligsahan?",
                    "answer": "Si Buwaya.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Sino ang nagsabing kawawa si Pagong dahil mabagal siyang gumalaw?",
                    "answer": "Si Elepante.",
                },
                {
                    "story_title": "Ang Pagong at ang Kuneho",
                    "question": "Ano ang sinabi ni Unggoy tungkol kay Pagong?",
                    "answer": "Kahit mabagal siya ay hindi naman siya tumitigil.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Sino ang nagmamaneho ng jeepney?",
                    "answer": "Si Tatay.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang suot ng taong sumakay na bukod-tangi?",
                    "answer": "Makulay at maluwang na damit.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Anong kulay ang malaking sapatos niya?",
                    "answer": "Pula.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang kulay ng kaniyang ilong?",
                    "answer": "Pula.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ilang bola ang inilabas niya mula sa kaniyang bulsa?",
                    "answer": "Limang bola.",
                },
                {
                    "story_title": "Isang Kakaibang Araw",
                    "question": "Ano ang ginawa ng mga tao nang saluhin niya ang mga bola?",
                    "answer": "Napalakpak silang lahat.",
                },
            ],
            "items": [
                {"type": "word", "text": word}
                for word in [
                    "Binti", "Pito", "Tubig", "Pagod", "Kanta",
                    "Regalo", "Butiki", "Halaman", "Malapot", "Gagamba",
                ]
            ] + [
                {"type": "sentence", "text": sentence}
                for sentence in [
                    "Naglalaba si Tatay sa palanggana.",
                    "Magpapalit ako ng kamiseta mamaya.",
                    "Nilinis nila ang agiw rito.",
                    "Bumili kami ng bagong suklay.",
                ]
            ] + [
                {"type": "paragraph", "text": passage["content"], "title": passage["title"]}
                for passage in [
                    {
                        "title": "Ang Pagong at ang Kuneho",
                        "content": "\"Ako ang pinakamabilis tumakbo,\" sabi ni Kuneho. \"Wala nang bibilis pa sa akin!\"\n\n\"Naku, Kuneho, wala ka nang ibang sinabi kung hindi gaano ka kabilis tumakbo,\" sabi ni Pagong. \"Hinahamon kita sa isang paligsahan.\"\n\n\"Hindi mo ako matatalo!\" sabi ni Kuneho. \"Dahil mas mabilis akong tumakbo!\"\n\n\"Malalaman natin 'yan bukas ng umaga,\" sabi naman ni Pagong.\n\n\"Kapana-panabik ito!\" sabi ni Buwaya.\n\n\"Kawawa naman si Pagong kasi ang bagal niyang gumalaw,\" sabi naman ni Elepante.\n\n\"Kahit mabagal siya ay hindi naman siya tumitigil,\" sabi ni Unggoy.\n\nKinabukasan, dumating ang lahat ng hayop upang manood ng paligsahan.",
                    },
                    {
                        "title": "Isang Kakaibang Araw",
                        "content": "Iba't ibang tao ang sumasakay sa jeepney ni Tatay. May mga estudyanteng papasok ng eskuwela. May aleng mamamalengke. May nanay na may kasamang anak.\n\nPero may isang taong sumakay na bukod-tangi. Ang suot niya'y makulay at maluwang na damit. Napakalaki ng sapatos niyang pula! Pula rin ang ilong niya. Puting-puti ang mukha niya at asul ang kulot niyang buhok.\n\nHindi ko siya mapigilang tingnan. Tinititigan din siya ng katabi niya.\n\nNgumiti siya sabay-labas ng limang bola mula sa kaniyang bulsa. Isa-isa niyang itinapon ang mga bola pataas at sinalo. Paulit-ulit niya itong ginawa. Napapalakpak kaming lahat!",
                    },
                ]
            ],
            "is_system_owned": True,
            "is_official_reading": True,
            "system_assessment_period": "eosy",
            "system_assessment_phase": "posttest",
            "assessment_set": "crla",
            "assessment_kind": "crla",
            "language": "Filipino",
            "type": "assessment",
            "source_type": "shared",
            "status": "published",
            "student_access": True,
            "is_active": True,
        }
        eosy.save()


class Migration(migrations.Migration):
    dependencies = [
        ("pabasa_app", "0061_seed_official_crla_assessments"),
    ]

    operations = [
        migrations.RunPython(update_official_crla_story_sets, migrations.RunPython.noop),
    ]
