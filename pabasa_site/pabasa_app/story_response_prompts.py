"""
Story Response Activity - Suggested Prompts

Organized by category and language for Grade 2 students.
These prompts encourage personal responses, reflections, and connections
rather than factual recall (which is for 5W's Story Questions).
"""

RESPONSE_PROMPT_CATEGORIES = {
    "feelings": {
        "emoji": "❤️",
        "label": "Feelings & Opinions",
        "description": "Personal reactions and preferences about the story"
    },
    "imagine": {
        "emoji": "💭",
        "label": "Imagine",
        "description": "Put yourself in the story"
    },
    "connect": {
        "emoji": "🌱",
        "label": "Connect",
        "description": "Relate the story to your own experiences"
    },
    "reflect": {
        "emoji": "⭐",
        "label": "Reflect",
        "description": "Deeper thinking about the story's meaning"
    },
    "predict": {
        "emoji": "🔮",
        "label": "Imagine What Happens Next",
        "description": "Think beyond the story's ending"
    }
}

SUGGESTED_PROMPTS = {
    "Filipino": {
        "feelings": [
            "Ano ang pinakanagustuhan mo sa kuwento?",
            "Aling bahagi ng kuwento ang pinakamasaya para sa iyo?",
            "Ano ang naramdaman mo habang pinapakinggan ang kuwento?",
            "Sino sa kuwento ang gusto mong makausap? Bakit?",
        ],
        "imagine": [
            "Kung ikaw ang tauhan sa kuwento, ano ang gagawin mo?",
            "Kung ikaw si Lito, ano ang gagawin mo pagkatapos makarating sa paaralan?",
            "Kung ikaw si Nena, paano mo aalagaan ang bulaklak?",
            "Kung ikaw si Rosa, ibabahagi mo rin ba ang iyong baon? Bakit?",
            "Kung ikaw si Joel, ano ang gagawin mo kapag nawala ang iyong lapis?",
            "Kung maaari kang sumali sa kuwento, ano ang gagawin mo?",
        ],
        "connect": [
            "May bahagi ba ng kuwento na katulad ng iyong karanasan?",
            "Ano ang bahagi ng umaga ni Lito na gusto mong gawin din?",
            "Ano ang masasabi mo tungkol sa paghahanda ni Lito sa pagpasok?",
            "Ano ang paborito mong gawain bago pumasok sa paaralan?",
            "Ano ang naramdaman mo tungkol sa pag-aalaga ni Nena sa halaman?",
            "May halaman ka ba na gusto mong alagaan? Bakit?",
            "Kung ikaw ang may bulaklak, saan mo ito ilalagay?",
            "May pagkakataon ba na nagbahagi ka ng pagkain sa isang kaibigan?",
            "Ano ang ibig sabihin ng pagiging mapagbigay para sa iyo?",
            "May pagkakataon ba na mawala ang isang bagay na mahalaga sa iyo? Paano mo naramdaman?",
        ],
        "reflect": [
            "Ano ang gusto mong baguhin sa kuwento?",
            "Ano ang natutuhan mo mula sa kuwento?",
            "Paano mo hahanapin ang isang bagay na nawala?",
            "Ano ang payo mo kay Joel?",
        ],
        "predict": [
            "Ano sa tingin mo ang maaaring mangyari pagkatapos ng kuwento?",
            "Ano pa ang gusto mong gawin nila sa parke?",
        ]
    },
    "English": {
        "feelings": [
            "What did you like most about the story?",
            "Which part of the story did you like best?",
            "How did the story make you feel?",
            "Who would you like to talk to in the story? Why?",
        ],
        "imagine": [
            "What would you do if you were in the story?",
            "What would you do if your ball rolled away?",
            "If you had a pet like Ben, what would you do with it?",
            "How would you take care of a little pet?",
            "If you had a big hat, when would you wear it?",
            "If you were the little fish, where would you like to swim?",
            "If you could join the story, what would you do?",
            "What would you choose to wear on a sunny day?",
            "If you were Mia, what would you do next?",
            "What kind of book would you like to have?",
        ],
        "connect": [
            "Does the story remind you of something in your life?",
            "What did you like about Ben and his pet?",
            "What would you like most about the story?",
            "Have you ever lost something you liked? How did you feel?",
            "What would you do if you had a book like Ana's?",
            "What do you like most about reading books?",
        ],
        "reflect": [
            "What would you change about the story?",
            "What did you learn from the story?",
            "What do you think the little fish might see next?",
        ],
        "predict": [
            "What do you think might happen next?",
            "What would be the next adventure for the character?",
        ]
    }
}

# Story-specific prompts (keyed by story title/identifier)
STORY_SPECIFIC_PROMPTS = {
    "english-set-1": {  # Ben and the Little Pet
        "language": "English",
        "Filipino_title": "Ben at ang Maliit na Alaga",
        "English_title": "Ben and the Little Pet",
        "prompts": {
            "feelings": [
                "What did you like about Ben and his pet?",
                "How did the story make you feel?",
            ],
            "imagine": [
                "If you had a pet like Ben, what would you do with it?",
                "How would you take care of a little pet?",
            ],
            "connect": [
                "Do you have a pet? What would you do with it?",
                "How would Ben's pet feel with you?",
            ],
        }
    },
    "english-set-2": {  # Mia and the Red Ball
        "language": "English",
        "English_title": "Mia and the Red Ball",
        "prompts": {
            "feelings": [
                "What was your favorite part of the story?",
            ],
            "imagine": [
                "What would you do if your ball rolled away?",
                "If you were Mia, what would you do next?",
            ],
            "connect": [
                "Have you ever lost something you liked? How did you feel?",
            ],
        }
    },
    "english-set-3": {  # Sam's Big Hat
        "language": "English",
        "English_title": "Sam's Big Hat",
        "prompts": {
            "feelings": [
                "What do you like about Sam's hat?",
                "What was your favorite part of the story?",
            ],
            "imagine": [
                "If you had a big hat, when would you wear it?",
                "What would you choose to wear on a sunny day?",
            ],
        }
    },
    "english-set-4": {  # The Little Fish
        "language": "English",
        "English_title": "The Little Fish",
        "prompts": {
            "imagine": [
                "If you were the little fish, where would you like to swim?",
                "What do you think the little fish might see next?",
            ],
            "connect": [
                "Would you like to swim like the little fish?",
            ],
        }
    },
    "english-set-5": {  # Ana's New Book
        "language": "English",
        "English_title": "Ana's New Book",
        "prompts": {
            "feelings": [
                "What do you like most about reading books?",
                "What was your favorite part of the story?",
            ],
            "imagine": [
                "What kind of book would you like to have?",
                "What would you do if you had a book like Ana's?",
            ],
        }
    },
    "filipino-set-1": {  # Ang Umaga ni Lito
        "language": "Filipino",
        "Filipino_title": "Ang Umaga ni Lito",
        "prompts": {
            "feelings": [
                "Ano ang pinakanagustuhan mo sa kuwento?",
            ],
            "imagine": [
                "Ang bahagi ng umaga ni Lito na gusto mong gawin din?",
                "Kung ikaw si Lito, ano ang gagawin mo bago pumasok sa paaralan?",
            ],
            "connect": [
                "Ano ang masasabi mo tungkol sa paghahanda ni Lito sa pagpasok?",
                "Ano ang paborito mong gawain bago pumasok sa paaralan?",
            ],
        }
    },
    "filipino-set-2": {  # Si Nena at ang Bulaklak
        "language": "Filipino",
        "Filipino_title": "Si Nena at ang Bulaklak",
        "prompts": {
            "imagine": [
                "Kung ikaw si Nena, paano mo aalagaan ang bulaklak?",
                "Kung ikaw ang may bulaklak, saan mo ito ilalagay?",
            ],
            "connect": [
                "Ano ang naramdaman mo tungkol sa pag-aalaga ni Nena sa halaman?",
                "May halaman ka ba na gusto mong alagaan? Bakit?",
            ],
        }
    },
    "filipino-set-3": {  # Ang Masayang Araw
        "language": "Filipino",
        "Filipino_title": "Ang Masayang Araw",
        "prompts": {
            "feelings": [
                "Anong bahagi ng kuwento ang nagpasaya sa iyo?",
            ],
            "imagine": [
                "Kung kasama ka nina Carlo at Ana, ano ang gusto mong gawin?",
                "Ano pa ang gusto mong gawin nila sa parke?",
            ],
            "connect": [
                "Ano ang paborito mong gawin sa parke?",
            ],
        }
    },
    "filipino-set-4": {  # Ang Baon ni Rosa
        "language": "Filipino",
        "Filipino_title": "Ang Baon ni Rosa",
        "prompts": {
            "imagine": [
                "Kung ikaw si Rosa, ibabahagi mo rin ba ang iyong baon? Bakit?",
            ],
            "connect": [
                "Ano ang naramdaman mo nang ibinahagi ni Rosa ang kanyang tinapay?",
                "May pagkakataon ba na nagbahagi ka ng pagkain sa isang kaibigan?",
            ],
            "reflect": [
                "Ano ang ibig sabihin ng pagiging mapagbigay para sa iyo?",
            ],
        }
    },
    "filipino-set-5": {  # Ang Nawalang Lapis
        "language": "Filipino",
        "Filipino_title": "Ang Nawalang Lapis",
        "prompts": {
            "imagine": [
                "Kung ikaw si Joel, ano ang gagawin mo kapag nawala ang iyong lapis?",
            ],
            "connect": [
                "Ano ang mararamdaman mo kung mawala ang isang bagay na mahalaga sa iyo?",
                "Paano mo hahanapin ang isang bagay na nawala?",
            ],
            "reflect": [
                "Ano ang payo mo kay Joel?",
            ],
        }
    }
}

def get_general_prompts(language="English"):
    """Get general prompts for a given language, organized by category."""
    language_key = "English" if language.lower() in ["english", "en"] else "Filipino"
    return SUGGESTED_PROMPTS.get(language_key, SUGGESTED_PROMPTS["English"])

def get_story_specific_prompts(story_key):
    """Get story-specific prompts if available for a given story."""
    return STORY_SPECIFIC_PROMPTS.get(story_key, None)

def get_all_prompts_for_story(story_key, language="English"):
    """
    Get combined prompts for a story: general + story-specific.
    Returns a dict organized by category.
    """
    language_key = "English" if language.lower() in ["english", "en"] else "Filipino"
    
    # Start with general prompts
    all_prompts = {}
    general = SUGGESTED_PROMPTS.get(language_key, {})
    for category, items in general.items():
        all_prompts[category] = {
            "type": "general",
            "items": items
        }
    
    # Overlay story-specific prompts
    story_specific = STORY_SPECIFIC_PROMPTS.get(story_key, {})
    if story_specific:
        story_prompts = story_specific.get("prompts", {})
        for category, items in story_prompts.items():
            if category in all_prompts:
                # Append story-specific to existing category
                all_prompts[category]["items"].extend(items)
            else:
                all_prompts[category] = {
                    "type": "story_specific",
                    "items": items
                }
    
    return all_prompts
