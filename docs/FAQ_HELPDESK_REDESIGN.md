# Pip's Help Desk — implementation and QA

October 22, 2026. Local target: `http://127.0.0.1:8000/faq/`.
**Local implementation only. Not deployed.**

## 1. Previous implementation and audit

The active route is `views.faq`, rendering
`pabasa_site/pabasa_app/templates/pabasa_app/faq.html`. The page previously loaded
`public_support.css`, also used by the public legal/support pages, and kept its
FAQ behavior in an inline script.

The previous page had a large hero, three category jump cards, three separate
question sections, 12 native-details accordions, and a generic support banner.
Its search **did work**: browser verification with `microphone` returned two
records by searching question/answer text. It did not index category labels or
keywords, provide a clear button, or present an actionable empty state.

Category cards were valid fragment links, not topic filters. Selecting Reading
updated the fragment; selected styling was driven by IntersectionObserver.
Native details opened an answer and supported multiple open questions. The
redesign preserves that multi-open interaction model using explicit buttons.

Inspected the shared navigation/footer, existing contact targets, responsive
rules, and the shared Andika font declaration in `css/typography.css` and
`includes/typography.html`. The production reference contained the same FAQ
collection and support destinations when inspected:
[production FAQ](https://tupcpabasa.app/faq/).

## 2. New structure

- Compact cream search hero with the original headline and supplied supporting
  copy. Pip sits behind a small Help Desk sign; there is one question bubble.
- Three editorial quick links, rather than another answer collection.
- One FAQ workspace: topic navigation on the left, filtered answers on the right.
- Six questions per page, with explicit result ranges and Previous/Next controls,
  to avoid replacing the old long stack with an even longer one.
- A single split support panel distinguishes classroom/account help from
  technical support.

No chatbot, live-agent interface, new backend API, framework, or dependency was
introduced. The existing `public_support.css` was left unchanged and is no
longer loaded by this FAQ template.

## 3. Search

The one semantic collection in `faq_questions.html` supplies every question,
answer, topic label, and keyword. The controller reads those records once.
Search, pagination, category counts, and quick links use the same records.

Search normalizes case, accents, punctuation, and surrounding/repeated whitespace.
Every query term must occur somewhere in the record's title, answer, topic label,
or keywords. Results retain editorial order and are deduplicated by record ID.
Filtering is synchronous and local; there is no artificial loading delay or
network request for a search.

The default is All Questions. Selecting a topic preserves the query and combines
the filters. The result context explicitly states the search and active topic;
topic counts show matches for the current query across each topic. Clear Search
clears only the query. Reset filters/Browse all topics clears both.

The no-results state includes its message, Clear Search, Browse all topics, and
a support link. One polite, atomic live region announces result counts/ranges.
Submitting search with Enter focuses the results heading.

## 4. Topics and navigation

Four compact native buttons: All Questions, Getting Started, Reading Activities,
and Accounts & Support. The selected button has `aria-pressed`, a navy/sky state,
and a yellow indicator. Choosing a topic changes the heading, count, range, and
visible records without reloading or explicitly scrolling the page.

Mobile uses a horizontally scrollable topic strip inside the page width.
Keyboard focus brings off-screen topic buttons into view. Legacy category
fragments (`faq-getting-started`, `faq-reading`, `faq-accounts`) are recognized
by the controller. New question fragments open their corresponding record.

## 5. Accordions and quick answers

Every question uses a native button with `aria-expanded` and `aria-controls`.
Answers remain part of the same surface, with a restrained cream background,
readable paragraphs/lists, and an explicit plus/minus indicator. Open answers
are not collapsed by opening another question. Their state remains in the same
DOM records while filters/pages change.

Quick answers select the correct topic/page, clear conflicting search text,
expand the existing record, and focus its question. Only the necessary scroll
brings the expanded article into view. Scrolling is immediate, avoiding delayed
access or unnecessary animated page movement. Answer/icon transitions are subtle
and disabled by the scoped reduced-motion rule.

All answers are server-rendered and readable without JavaScript; a noscript
message explains that interactive search/topic filtering requires JavaScript.
The three quick links are editorial selections, not claims about usage analytics.

## 6. Content refinements and source checks

All 12 original question titles/topics remain covered. Answers were rewritten
in plain English, with short instructions and fewer implementation terms.

| Area | Verified source / refinement |
| --- | --- |
| Student registration/enrollment | `register_student`, `_complete_student_signup`, `_signup_section_for_request`: signup resolves an existing school section and enrolls the student after registration completes. Removed “canonical class” terminology and told families to ask school staff about missing/wrong sections. |
| Verification | Registration and password recovery have configuration-dependent OTP paths. Replaced the old unconditional “after OTP verification” explanation with instructions to follow the actual form. Resend replaces the pending code. |
| Account access | `auth.html` labels the credential **PABASA ID**, not email. Added direct sign-in guidance and a route to school staff for school-managed access. |
| Teacher scope | Existing teacher dashboard/material/review and Live Assessment views apply class/teacher boundaries. The answer refers to assigned classes rather than unrestricted class management. |
| Official CRLA | `_reader_assessment_state`, `_assessment_workflow_context`, `assessment`, and Live Assessment entry/control/waiting-room views gate availability, teacher ownership, and selected participants. Added teacher-guided access instructions; no unrestricted retake advice. |
| ARAL / Supplementary | `assessment.html`, assessment workflow, and `_student_has_current_supplementary_material_access`: prescribed lessons and released/assigned current-class supplementary work are distinct from Practice Mode. No blanket availability claim. |
| Languages | `practice` uses Filipino/English language options; other material/activity language follows its content. The answer does not promise translations of every activity. |
| Automatic/manual checking | `teacher_prescribed_review.html` explicitly identifies Session 9 drawings as requiring a teacher decision. Clarified that supported automatic checking does not cover every response. |
| Microphone | `basahin.js` uses getUserMedia/MediaRecorder and handles unavailable capture; `assessment_reader.js` has microphone selection/testing and its Chrome/Edge error guidance. Selector/test instructions are qualified with “where available.” |
| Narration and activity errors | Existing activities expose Pakinggan/Read Aloud controls and save/error states. Advice uses the actual available controls, avoids repeated submissions, and sends official-assessment interruptions to the teacher. |
| Interruption/recovery | `crla_recovery.js` and `live_assessment_recovery_validation` support teacher-side saved-session recovery with validation. The answer does not guarantee recovery, discard a draft, or recommend a new official attempt. |
| Progress | Existing assessment records, current enrollment checks, and teacher-review states distinguish saved work from pending review. Advice asks the teacher to check the correct account/class before repeating anything. |
| Password recovery | Existing forgot-password routes use the account email and displayed verification steps. Unknown school-managed email goes to school staff. |
| Devices | Responsive pages do not guarantee microphone/recording support on every device. The answer now makes that distinction and avoids universal compatibility promises. |

The browser's permission and secure-context requirements were also checked
against [MDN's getUserMedia documentation](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).
No backend behavior was changed to support these explanations.

The audit found oversimplifications, especially mandatory OTP wording and
unqualified device expectations, rather than evidence that every old answer was
wrong. Live deployment configuration was not changed or independently audited;
the revised instructions deliberately do not assume a particular OTP setting.

## 7. Added/removed questions

**Retained:** all 12 original questions. **Removed:** none.

Seven additions, for **19 total**:

1. How can I access my account?
2. How do I join a CRLA Live Assessment?
3. Does PABASA check activities automatically?
4. What should I do if my microphone is not working?
5. What should I do if an activity is not working?
6. What if an official reading assessment is interrupted?
7. Why is my activity progress not appearing?

The collection contains 4 Getting Started, 10 Reading Activities, and 5
Accounts & Support questions. Expanded content is not duplicated in shortcuts,
search results, or topic lists.

## 8. Support paths

Class assignments, assessment schedules, assigned activities, and school-managed
accounts go to the teacher/school coordinator. Website and technical issues go
to the development team.

Preserved the existing `mailto:pabasa.tupc@gmail.com` destination. The original
phone link, `tel:+639063979666`, remains in the contact answer. Both match the
existing source and inspected production FAQ. No new contact address was
invented. No email or phone call was sent to test delivery.

## 9. Pip and typography

Reused the existing `images/footer-mascot.webp` Pip artwork in the hero. Its
transparent margins are accommodated by the support-desk frame; `object-fit:
contain` preserves the character's proportions. No generated artwork or new
image asset was needed. Pip is not repeated in questions or topic controls.

All sampled headings, controls, and body text compute to the existing
`Andika, sans-serif` family. Shared font declarations were not edited.

## 10. Files

- Modified `pabasa_site/pabasa_app/templates/pabasa_app/faq.html`.
- Added `pabasa_site/pabasa_app/templates/pabasa_app/faq_questions.html`.
- Added `pabasa_site/pabasa_app/static/pabasa_app/faq_helpdesk.css`.
- Added `pabasa_site/pabasa_app/static/pabasa_app/js/faq_helpdesk.js`.
- Added `tools/test_faq_helpdesk.cjs`.
- Added this report.

The About redesign, homepage, What Is PABASA, shared navigation/footer,
authentication, assessment/STT/scoring workflows, progress calculations, models,
and dependencies were not edited. The pre-existing local database modification
was preserved. No migrations or cloud operations were run.

## 11. Responsive inspection

Checked full-page captures and DOM layout bounds at CSS widths **320, 375, 430,
768, 1024, 1440, 1920, and 2560**, at 1000px CSS height. Also checked a
**2560×1440** viewport.

The connected browser's 80% application scale rounds the requested 1366px
setting to **1367 CSS pixels**. Both **1365 and 1367** were checked. Exact 1366px
is not claimed as tested.

The first mobile pass found an intrinsic-width issue in the topic strip. Fixed
the grid's minimum track size and the sidebar's minimum width, then retested all
nine requested settings. Final samples had no overflowing hero/search/results/
question/support bounds. Mobile topic overflow stays inside its own scroll strip.
Pip loaded at every size. The help content is constrained to 1248px on the large
monitor, with normal text sizes rather than proportional shrinking.

Inspected desktop/mobile default views, all responsive contact-sheet layouts,
search results, no results, expanded troubleshooting, and the support panel.
At 320px, the expanded activity answer had no internal horizontal overflow;
the quick link placed the question and beginning of the answer below the header.

## 12. Accessibility inspection

Verified in the rendered browser:

- Labeled search, working clear control, and polite atomic result announcements.
- Native topic buttons with selected state and current match counts.
- Question button/answer relationships and correct expanded states.
- Enter/Space activation, multiple open answers, search Enter focus, and quick
  answer focus on the correct question.
- Keyboard reachability of mobile topic buttons within the scroll strip.
- Visible focus styles and sensible heading order.

Calculated palette contrast ratios: body on cream **5.31:1**; answer text on
cream **7.13:1**; selected topic **8.86:1**; question topic labels **5.01:1**;
search placeholder **4.62:1**; search focus ring on cream **4.67:1**; support
button text **9.89:1**. These sampled normal text pairs exceed 4.5:1, and the
focus-ring sample exceeds 3:1. This is a targeted contrast check, not a claim
of a complete WCAG conformance audit.

Reduced-motion CSS disables answer/icon transitions and animations. The
browser connector does not expose media-preference emulation, so reduced motion
was inspected in source rather than tested with the preference enabled.
A full assistive-technology session was not performed.

## 13. Functional and regression results

- `python pabasa_site/manage.py check`: **passed**, no issues.
- `python pabasa_site/manage.py test pabasa_app.tests_static_images --verbosity 1`:
  **25 existing tests passed**.
- `node --test tools/test_faq_helpdesk.cjs`: **7 focused tests passed**, including
  normalization, title/answer/category/keyword matching, combined filters,
  deduplication, pagination boundaries/coverage, and quick-link record resolution.
  The tests read the actual FAQ collection rather than another answer fixture.
- Browser assertions passed for mixed-case/whitespace search; answer-only and
  keyword queries; category-label search; combined scope/query preservation;
  clear/reset/no-results recovery; all 19 records across four result pages;
  quick links to the second topic page; Enter/Space; and multiple open answers.
- `microphone` matched five actual records, including oral reading, microphone
  access, and microphone troubleshooting. Accounts & Support plus that query
  narrowed the result to the device question, with the combined scope shown.
- A content audit confirmed all 12 original question titles are still present.
- An anonymous Django render returned HTTP 200; all 9 distinct internal link
  destinations in the rendered page resolved to existing routes.
- Legacy topic fragments and a direct question fragment were verified in the
  browser; the question fragment selected its topic and opened its answer.
- Shared header/footer markup matched the before capture exactly. Header
  dimensions matched at 1440px. Their source/style files were not edited.
- No warnings/errors were returned by the inspected browser console log.
- `git diff --check`: **passed**; only the repository's normal CRLF/LF notice
  was printed for the edited template.

## 14. Remaining limitations and evidence

- Exact 1366px is bracketed as described above.
- Reduced-motion preference emulation, a full screen-reader session, other
  browser engines, and physical device recording tests were not performed.
- Mailbox delivery/phone availability were not tested by sending a message or
  making a call; destinations were verified against existing source/production.
- FAQ instructions were checked against local implementation. No authenticated
  student assessment, recording, account creation, or submission was performed.
- With JavaScript disabled, answers remain readable but interactive filtering
  and pagination are unavailable, as the page explains.

Screenshots and JSON evidence live outside source control at:

`C:/Users/iamdo/.codex/visualizations/2026/10/22/01a16113-8044-7d92-beda-6242b47e3b4d/faq-qa/`

Useful evidence: `helpdesk-desktop.jpg`, `helpdesk-mobile.jpg`,
`search-microphone-desktop.jpg`, `mobile-activity-answer.jpg`,
`empty-state-desktop.jpg`, `responsive-contact.jpg`, `responsive-checks.json`,
`functional-checks.json`, and `shared-before.json` / `shared-after.json`.

## 15. Status

Ready for local review at `/faq/`. **Not deployed.**
