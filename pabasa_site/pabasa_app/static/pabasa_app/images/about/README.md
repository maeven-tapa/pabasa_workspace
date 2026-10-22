# About exhibition interface captures

Captured locally on October 22, 2026 from the existing PABASA templates.
These are interface examples, not historical research evidence or student results.

- `phrase-reading-board.webp`: `phrase_reading_page.html` and its existing
  `phrase_reading.js` controller, at the envelope selection screen.
- `phrase-reading-guidance.webp`: the same activity after selecting an envelope.
  The public sample phrase “the happy puppy” comes from that template's existing
  introduction. No recording or assessment was submitted.
- `student-monitor.webp`: the actual monitor markup and styles from
  `live_assessment_session.html`, rendered with an empty participant list.
  The capture is cropped around the monitor; it contains no learner records.

The temporary capture HTML used the existing Django template engine and static
assets. Speech, persistence, authentication, and session scripts were excluded.
The activity UI used its existing controller; its introductory overlay was
excluded to capture the activity underneath. No application templates, views,
APIs, sessions, or database records were modified to obtain these captures.
The temporary HTML was removed after capture.

WebP conversion removes unpainted screenshot margins from the in-app browser.
The screenshots are displayed with their proportions preserved and are labeled
as non-playable previews. No synthetic student names, scores, or results appear.
