# PABASA Help Center refinement

Date: October 22, 2026. Target: `http://127.0.0.1:8000/faq/`. Status: implemented locally; not deployed.

This pass refines the existing Pip’s Help Desk. The cream hero, same Pip artwork, search, quick answers, two-column workspace, topic filters, multiple-open accordions, pagination and split support destination remain in place. All 19 FAQ records are preserved byte-for-byte.

## 1. Initial audit findings

The live local rendering and the active Django template, FAQ stylesheet, controller, question collection and shared header-height implementation were inspected before edits. Baseline source copies and desktop/mobile screenshots were saved outside the repository.

- The navy mascot caption looked detached from the cream hero.
- Quick links were visually weak and distant from their heading.
- Repeated category labels and full-width row rules added noise.
- The sidebar contained two permanent instructions that did not help navigation.
- Sidebar sticky positioning used a fixed offset. Browser inspection additionally found that shared body overflow created a non-scrolling ancestor, preventing actual sticky behavior.
- Six questions per page gave 19 records four pages, with a single question on the last page.
- Small metadata and supporting text needed a more consistent scale.

## 2. Visual refinements

The workspace now has one pale-blue containing surface around the compact topic navigator and white answers panel. Softer separators, consistent borders, spacing tokens and restrained navy/yellow details connect it to the hero. No sections, libraries, illustrations or decorative cards were added.

## 3. Hero

The existing mascot remains in its arch, with a lightweight navy caption directly on the cream background. The dark caption block was removed. The headline is unchanged; its yellow underline is thinner and positioned below the letterforms.

The supporting copy is now: “Have a question about PABASA? Search for an answer or browse the topics below.” Search has a 64px outer field, 16px input text, aligned icon, 44px clear control and a visible focus ring. The redundant visible scope sentence was replaced with screen-reader instructions.

At a 1440px viewport the hero decreased from about 370.5px to 341.9px. At 375px it decreased from about 484.7px to 460.2px. The compact mobile mascot remains after search.

## 4. Quick answers

“Quick answers” now introduces three compact bordered pills with directional icons, hover feedback and visible keyboard focus. No popularity claim is made. All shortcuts use the same underlying HTML records. Browser tests verified all three clear conflicting searches, select the correct topic/page, expand the actual answer and focus its question without hiding it under the header.

## 5. Topic sidebar

Removed “Questions for every step” and the multiple-open explanation. Kept a compact support shortcut, aligned counts, consistent icons and the blue/yellow selected state. The measured desktop sidebar height decreased from about 454.7px to 362px.

Sticky positioning reads the existing `--public-header-height` token. A FAQ-only `body:has([data-helpdesk])` overflow correction allows native sticky positioning to work; no shared template or navigation stylesheet was edited. Browser measurements verified a 78px sidebar top with the 62px header, then containment at the workspace bottom. A ResizeObserver and resize listener disable sticking when the sidebar does not fit the viewport. A 400px-high desktop window used normal flow. Tablet/mobile use normal flow and compact topic navigation. Mobile focus outlines sit inside each topic button to avoid clipping in the scrollable selector. Quick answers and resizing also bring the active topic fully into view by scrolling only that horizontal selector; browser checks covered Reading and Accounts at 375px and a desktop-to-320px resize.

## 6. Questions and answers

Question titles use balanced padding, quieter dividers, a compact plus/minus indicator and visible keyboard focus. Category labels appear once per consecutive group when browsing all topics or mixed search results. They disappear when one topic is selected.

Expanded answers use a pale-blue background and restrained left accent. Paragraph/list spacing is consistent; long text is constrained to 72ch. Standalone answer links have comfortable target height. Multiple-open behavior is preserved, including when leaving and returning to a results page. No answers were rewritten, added or removed during this refinement.

## 7. Pagination

The default is now eight questions, using one shared JavaScript constant. All Questions has three pages of 8/8/3; Reading Activities has 8/2. Topic/query changes reset to a valid first page; the helper also clamps invalid page indices. Previous/Next retain the topic/query and preserve open-answer state, while moving focus to the results heading.

This was measured rather than changed without review: the closed 1440px answer panel increased from approximately 642.8px with six old rows to 676.7px with eight refined rows, a 33.9px increase for two additional questions. At 375px the increase is about 144px. This reduces navigation while keeping mobile rows readable.

## 8. Support destination

The light-blue panel now has a navy top rule, balanced icon treatments, a central desktop divider and stacked mobile paths. It uses the requested shorter description and classroom/technical copy. Redundant contact-person lines were consolidated into that copy.

The existing `mailto:pabasa.tupc@gmail.com` action and visible address remain. The central FAQ collection also retains its existing telephone destination. The password/verification-code reminder remains as a readable 13px note. Contact destinations were inspected; no email was sent or deliverability claimed.

## 9. Typography and spacing

Andika remains the computed font at every tested width. Small metadata uses a shared scale; category/navigation labels were enlarged, answer text remains comfortable, and search text stays at 16px on mobile. Shared spacing tokens govern the main panels. Hero, shortcut strip, intro and workspace transitions were tightened. No unrelated typography rules were changed.

## 10. Responsive verification

Rendered screenshots were captured and inspected. Final DOM measurements found no horizontal page overflow or clipped FAQ buttons; visible FAQ actions measured at least 44px high.

| CSS viewport | Layout | Result |
|---|---|---|
| 320 × 1000 | Compact hero; horizontal topics; stacked support | No overflow/clipped controls |
| 375 × 1000 | Compact hero; horizontal topics; stacked support | No overflow/clipped controls |
| 430 × 1000 | Compact hero; horizontal topics; stacked support | No overflow/clipped controls |
| 768 × 1000 | Split hero; horizontal topic grid | No overflow/clipped controls |
| 1024 × 1000 | Two-column workspace; sticky topics | No overflow/clipped controls |
| 1365 and 1367 × 1000 | Two-column workspace; sticky topics | No overflow/clipped controls |
| 1440 × 1000 | Two-column workspace; sticky topics | No overflow/clipped controls |
| 1920 × 1000 | Constrained large-desktop composition | No overflow/clipped controls |
| 2560 × 1440 | Constrained large-monitor composition | No overflow/clipped controls |

The browser viewport API at the current app zoom cannot produce exactly 1366 CSS pixels with integer physical dimensions, so 1365 and 1367 were checked on either side. Open answers were also resized through 320 → 768 → 1440 without losing expansion or introducing overflow.

## 11. Accessibility verification

Browser checks confirmed native buttons, unique IDs, valid `aria-controls` / `aria-labelledby` relationships for all 19 accordions, consistent `aria-expanded` and answer visibility, a labelled search input, polite live result announcements, Enter/Space activation, visible focus and logical Tab movement into answer links and between topics. Quick-answer and pagination focus destinations were verified.

Calculated contrast ratios for the actual CSS colors: supporting hero text 5.31:1, white-surface metadata 5.52:1, category labels 5.01:1, answer text 6.86:1, placeholder 4.62:1, support copy 5.81:1, security note 4.75:1, email action 9.89:1. Reduced-motion rules disable FAQ transitions/reveals and native smooth anchor scrolling on this page; the media rule was inspected, not emulated in the browser.

## 12. Functional regression results

- Search matches titles, answers, topic labels and keywords, with case/whitespace/punctuation normalization and no duplicates.
- “microphone” gives 5 total results, with topic counts 0 Getting Started / 4 Reading / 1 Accounts. Combined filtering and category changes preserve the query.
- Empty results, clear-search and reset controls work. Enter in search moves focus to the summary.
- All 19 unique records appear across the three pages; no record is lost or duplicated. Last-page filtering and clearing return to valid results.
- Multiple answers remain open, native Enter/Space toggles work, and pagination preserves expansion consistently.
- Every quick-answer destination resolves and opens the correct central record. A direct link to `help-missing-progress` selects Reading page 2 and expands it.
- Support destinations remain valid; nine internal link destinations resolve through Django.
- Active mobile topics remain fully visible after shortcuts and viewport changes.
- Anonymous FAQ render: HTTP 200, with 19 records.
- `python pabasa_site/manage.py check`: no issues.
- `python pabasa_site/manage.py test pabasa_app.tests_static_images --verbosity 1`: 25 tests passed.
- `node --test tools/test_faq_helpdesk.cjs`: 7 tests passed, including real dataset search, combined filters, pagination coverage/clamping and deep-link page selection.
- Browser console: no captured warnings/errors in the final check.
- Shared `base.html` and the 19-question collection match their pre-refinement SHA-256 hashes. Existing unrelated local changes were preserved.

## 13. Files modified in this refinement

- `pabasa_site/pabasa_app/templates/pabasa_app/faq.html` — copy, caption/shortcut presentation and sidebar simplification.
- `pabasa_site/pabasa_app/static/pabasa_app/faq_helpdesk.css` — scoped visual, responsive, sticky, focus and motion refinements.
- `pabasa_site/pabasa_app/static/pabasa_app/js/faq_helpdesk.js` — eight-item default, conditional category grouping, adaptive sticky eligibility and active-topic visibility in the mobile selector.
- `tools/test_faq_helpdesk.cjs` — updated pagination expectations and later-page deep-link coverage.
- `docs/FAQ_HELPDESK_REFINEMENT.md` — this report.

The prior redesign’s untracked question collection/report were preserved. Existing runtime database changes were not reverted. No new asset paths or dependencies were introduced. The same `footer-mascot.webp` is reused.

## 14. Evidence and remaining limitations

Evidence directory: `C:/Users/iamdo/.codex/visualizations/2026/10/22/01a16113-8044-7d92-beda-6242b47e3b4d/faq-refinement-qa/`.

| Required view | Screenshot |
|---|---|
| Desktop hero | `desktop-hero-final.jpg` |
| Quick-answer strip | `quick-strip-final.jpg` |
| All Questions workspace | `all-questions-workspace-final.jpg` |
| Specific topic | `category-workspace.jpg` |
| Expanded answers | `expanded-answer.jpg` |
| Search results | `search-results.jpg` |
| Empty results | `no-results.jpg` |
| Pagination | `pagination.jpg` |
| Support | `support-final.jpg` |
| Mobile hero | `mobile-hero-final.jpg` |
| Mobile FAQ | `mobile-workspace-final.jpg` |
| Large monitor | `large-monitor-final.jpg` |
| Before/after | `before-after-desktop.jpg` |

Screenshots for earlier interaction states preceded the final sticky/focus correction; final viewport screenshots and sticky evidence document the corrected behavior. JSON files contain final responsive metrics, functional checks, keyboard/resize checks, semantics, contrast and console results.

Verification used the available Chromium-based in-app browser. Real-device Safari/Firefox, screen-reader software, operating-system reduced-motion emulation, authenticated reading workflows and email delivery were not tested. Those authenticated workflows were outside this frontend scope. Exact 1366px coverage is bracketed as described above. No missing assets were found.

## 15. Local/deployment status

The refinement is available on the running local `/faq/` page. No deployment, backend/API/model/authentication/assessment changes or edits to About, What Is PABASA, the homepage, shared navigation or shared footer files were made.
