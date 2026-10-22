# Supplementary activity configuration audit

Audited on October 22, 2026. Scope: the teacher's 16 Supplementary creation
cards in `pabasa_site/pabasa_app/templates/pabasa_app/courses.html`.

## Findings before implementation

All 16 cards were inspected before editing initialization or progression.

| # | Template | Required configuration | Finding |
|---|---|---|---|
| 01 | Letter & Sound Matching | Language, reading set | Renderer replaces an empty selection with the first set; no placeholder. |
| 02 | Sound Detective | Language, sound set, picture words | Set placeholder already exists; shared interaction flag can disagree with state after rerender. |
| 03 | Match the Letter to Its Sound | Language, reading set | Getter/synchronizer chooses first set; no placeholder. |
| 04 | Clap & Count Syllables | Language, word set, words, count | Set placeholder exists; displayed count can differ from stored count after Select All. |
| 05 | Syllable Blending | Language, activity format, prebuilt activity | Format placeholder exists; progression relies on a separate interaction flag. |
| 06 | Picture-Word Matching | Language, prescribed set or complete custom set | Normalizer/preview chooses first prescribed set; custom readiness accepts too few items. Prescribed/custom mode is an intentional default. |
| 07 | Decode the Word | Language, reading set | Getter/synchronizer chooses first set; no placeholder. |
| 08 | Word Meaning Match | Language, vocabulary reading set | Synchronizer chooses first set; no placeholder. |
| 09 | Phrase Reading Practice | Language, prescribed phrase set | Synchronizer and cards choose first set. Item checkboxes are intentionally fixed after choosing a set. |
| 10 | Sentence Reading Practice | Language, prescribed sentence set | State stays blank but renderer highlights first set. Item checkboxes are intentionally fixed after choosing a set. |
| 11 | Fluency Reading | Language, passage reading set | Shares the vocabulary synchronizer's first-set fallback; no placeholder. |
| 12 | Story Reading | Language, prescribed story | State stays blank but renderer highlights first story. |
| 13 | 5W's Story Questions | Published story, language, five questions with answers | Story placeholder exists; selector is moved outside the observed configuration container. Saved story selection is not restored into its dedicated state. |
| 14 | Retell the Story | Published Story Reading activity | Placeholder exists; async initialization and changes do not explicitly recompute progression. Repeated renders attach duplicate change handlers. |
| 15 | Story Response | Language, published story, suggested/custom prompt | Async load selects first story. Saved story/prompt/options are not restored into dedicated state. Repeated renders retain old event handlers. |
| 16 | Reading Practice | Title, reading items, language, week; existing status rules | Separate personal-material editor already clears language/week for creation. Fixed assessment type and Published status are intentional; preserve them. |

The first 15 cards also clear initial state, then repopulate some choices during
rendering. Schedule readiness separately requires `__teacherSelectedConfiguration`.
These competing sources of truth cause a visible selection to disagree with
validation. Some handlers replace the event target before the change bubbles.
Access readiness also ignores an earlier configuration being cleared.

## Implementation and verification

The shared `findTemplateConfigurationSelection` helper resolves explicit IDs
without choosing a fallback. Synchronizers, selectors, preview rendering, and
form serialization now keep blank selections blank. Required dropdowns have
empty-value placeholders, and card selectors do not highlight an unchosen set.

Progression uses the existing save validator and the current activity state,
instead of an interaction flag. Rendering, typed input, selection changes, and
asynchronous story loading reevaluate that state. Clearing an earlier
prerequisite locks both Schedule and Access, even if weeks remain checked.
Week-selection mechanics are unchanged.

Edits restore saved IDs before rendering. Story Response also restores the
prompt, prompt source, and narration/recording options; 5W restores its source
story. Valid older 5W activities with fewer questions retain their existing edit
validation. Async story responses cannot overwrite a subsequently opened panel.
Clap & Count keeps its existing count default, capped to the selected word count
when words are selected, so the displayed number matches the value validated.

Preserved defaults include prescribed/custom mode, fixed assessment type,
Published status, retry/randomization options, and narration/recording options.
No predefined catalog, item ordering, CSS style block, student implementation,
audio asset, scoring code, database schema, or persistence endpoint was changed.

### Automated verification

`tools/test_supplementary_configuration.cjs` executes the actual production
configuration functions and catalog data in jsdom, using synthetic stories and
mocked network responses. It tests all 16 cards individually. Cards 01–15 cover:

- Blank creation state and empty previews; placeholder save rejection.
- Direct first-option selection and alternate options, in both languages where
  applicable. Retell selects a published story and retains its existing language
  handling.
- Immediate schedule/access readiness and relocking after a selection clears.
- Preview/state consistency, create and update POST payloads, and restoration of
  saved configurations without another interaction.

Card 16 covers empty language/week state, protection against contextual language
autoselection, and dependent controls. Its actual Django create/update endpoints
are separately covered by the new
`test_reading_practice_can_be_created_and_edited_with_explicit_language_and_week`
test in `tests_template_activity_edit.py`; it passes and preserves record identity.

Additional regressions cover programmatic Set 1 selection without `change`, the
five-item custom picture limit, Clap & Count's displayed count, saved custom
response options, late asynchronous responses, and legacy 5W editing.

Result: **37 frontend checks passed**. The local browser also confirmed the
original phonics reproduction: blank set and locked Schedule; direct selection
of Filipino Set 1 enables Schedule; choosing a week enables Assignment; clearing
the set relocks both and empties the preview.

The jsdom check requires Node 24, jsdom 26.1.0 on `NODE_PATH`, and the repository's
Python 3.13 environment (`PABASA_TEST_PYTHON` can override the default `.venv`).
It loads static catalogs with an in-memory SQLite setting and does not read or
write real classroom data:

```powershell
node --test tools/test_supplementary_configuration.cjs
```

### Django verification and existing failures

`manage.py check` and `git diff --check` pass. Across the focused Django runs,
41 of 47 tests passed: `tests_template_activity_edit`,
`tests_aral_template_activities`, `tests_supplementary_term_lifecycle`, and the
new Reading Practice create/edit test. The six failures were individually
reproduced with the original `courses.html` loaded through a temporary template
override, without modifying the working checkout:

| Test | Existing failure |
|---|---|
| `test_template_update_preserves_record_and_template_payload` | Expects `["Week 2"]`, while persistence returns `[2]`. |
| `test_fluency_completion_calculates_cwpm_and_persists_transcript` | Student endpoint returns 403. |
| `test_fluency_completion_ignores_non_fluency_completed_results` | Student endpoint returns 403. |
| `test_fluency_no_speech_does_not_create_false_completion` | Returns 403 before the expected no-speech response. |
| `test_vocabulary_completion_is_server_scored_saved_and_idempotent` | Student endpoint returns 403. |
| `test_vocabulary_completion_rejects_incomplete_or_unmastered_answers` | Returns 403 before answer validation. |

These failures were left unchanged; week persistence, authorization, and learner
scoring are outside this configuration fix. Frontend save tests use synthetic
responses and do not establish full authenticated end-to-end database coverage
for every template. Production data and the existing local database changes
were preserved.
