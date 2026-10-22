# Authentication background standardization

Date: October 22, 2026 (Asia/Manila). Status: implemented locally; not deployed.

All eight active authentication templates now use the exact approved Login photograph through one shared background definition. Their in-page registration, OTP, validation, loading and completion states retain that shared background. No form redesign or authentication logic change was made.

## 1. Confirmed root cause

The active Django application is `pabasa_site/pabasa_app/`. Seven entry/recovery templates previously extended `base.html` directly and each defined its own inline body background. This was template-level duplication, rather than JavaScript changing the image or responsive queries substituting photographs.

Login and the account chooser already used the deployment PNG. Teacher/student signup and the three recovery templates retained `read.jpg` plus a dark gradient. The static asset handling resolved that old JPEG to `read.avif` in the browser. A separate principal temporary-password template used a pale gradient. Login also had an opaque white loading-screen background.

The unused legacy `static/pabasa_app/auth.css` contains another stock-image reference, but no active authentication template loads it. It was left untouched rather than deleting unrelated legacy styling.

## 2. Approved original asset

`pabasa_site/pabasa_app/static/pabasa_app/images/log-in_sign-up.png`

The existing PNG is 1448 × 1086 pixels and 2,239,393 bytes (about 2.14 MiB). It was preserved byte-for-byte. No duplicate, replacement, download, generated image or new image dependency was introduced. No optimized sibling was found; optimization of the approved asset was not included in this background-only change.

The actual Login reference was inspected in the browser: centered positioning, `background-size: cover`, no repeat, scroll attachment, and no dark overlay. That exact presentation is now shared. The old recovery/signup dark gradients were removed to match Login; card transparency and blur remain unchanged.

## 3. Authentication pages and states audited

| Existing interface | Previous background | Current treatment / verification |
|---|---|---|
| `/auth/` | Approved deployment PNG | Same PNG; desktop/mobile screenshots pixel-identical |
| Login loading layer | White | Shared image token; computed background verified without logging in |
| `/signup/` role chooser | Approved deployment PNG | Same PNG; browser inspected |
| `/signup/teacher/` | Stock `read.jpg` plus gradient | Approved PNG; first and second steps browser inspected |
| `/signup/student/` | Stock `read.jpg` plus gradient | Approved PNG; first and second steps browser inspected |
| Registration account/privacy steps, OTP, resend/error and success panels | In-page states of the signup templates | Shared root background; original markup/scripts preserved; no registration submitted |
| `/forgot-password/` | Stock `read.jpg` plus gradient | Approved PNG; live page and isolated error template inspected |
| `/forgot-password/otp/` | Stock `read.jpg` plus gradient | Approved PNG; live page and isolated error template inspected |
| `/forgot-password/reset/`, reset errors and success | Stock `read.jpg` plus gradient | Approved PNG; isolated Django-rendered template previews inspected |
| `/account/principal/change-temporary-password/` and errors | Pale gradient | Approved PNG; isolated Django-rendered template previews inspected |

Recovery resends redirect to existing screens; registration verification/resend endpoints return JSON and update the existing signup page. No additional authentication screens were invented. Email messages and generic Django error pages are not authentication page backgrounds and were not modified.

## 4. Background references replaced

Removed the five duplicated stock-image/gradient declarations from teacher signup, student signup, forgot password, recovery OTP and reset password. Removed the two duplicate approved-image declarations from Login and role selection after moving them to the shared component. Replaced the standalone temporary-password gradient with the same component. Removed the white loading-screen background so it uses the shared token.

There are no remaining page-specific background-image overrides in these active authentication templates.

## 5. Shared styling approach

`auth_base.html` extends the existing shared base, includes `includes/auth_background.html`, and exposes an `auth_extra_head` block for each page’s unchanged styles. Seven templates now inherit this authentication base. The standalone principal template includes the same background component and receives the `auth-layout` class without changing its card or controls.

The component defines `--auth-background-image` once using Django’s `{% static %}` tag. Both the authentication body and Login loading layer use it. The body background retains the existing necessary `!important` because the shared public-page body background is already important. No competing patch stack or JavaScript background controller was added. Existing scrolling, dimensions, typography and form CSS were preserved.

## 6. Files modified

New shared templates:

- `pabasa_site/pabasa_app/templates/pabasa_app/auth_base.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/includes/auth_background.html`

Updated authentication templates:

- `pabasa_site/pabasa_app/templates/pabasa_app/auth.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/signup.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/teacher_signup.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/student_signup.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/forgot_password.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/forgot_password_otp.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/forgot_password_reset.html`
- `pabasa_site/pabasa_app/templates/pabasa_app/principal_change_temporary_password.html`

Documentation: `docs/AUTH_BACKGROUND_STANDARDIZATION.md`.

The shared `base.html`, views, URL configuration, models and original photograph have unchanged SHA-256 hashes. All eight templates’ forms and scripts match their pre-change source. Existing runtime database modifications were preserved. No homepage, About, FAQ, What Is PABASA or dashboard files were edited.

## 7. Responsive and visual verification

Live browser checks covered Login, role choice, teacher signup, student signup, forgot password and recovery OTP at 320, 375, 430, 768, 1024, 1440, 1920 and 2560 CSS pixels. The requested 1366px was bracketed by 1365 and 1367px because integer viewport dimensions at the app’s current zoom cannot yield exactly 1366px. This produced 60 live page/viewport measurements. Most viewports were 1000px high; the 2560px case was 1440px high.

Reset and principal temporary-password templates were additionally checked across the same width range using isolated rendered previews. Reset success/errors and recovery errors were inspected at desktop/mobile sizes. These previews used synthetic context and did not bypass live authentication checks.

Findings:

- Every inspected page resolves the exact same approved image URL.
- Computed presentation is consistently `cover`, centered, no repeat and scroll attachment.
- No horizontal page overflow was found. The background covers the authentication document, including long forms.
- Desktop/mobile card widths, surface colors, borders, radii, fonts, shadows and backdrop blur match the baseline.
- Decoded Login screenshot comparisons at 1440 × 1000 and 375 × 1000 found no differing pixels.
- Registration step navigation retains the shared photograph. Synthetic names/birth dates were used only to move to the second step; no account details were submitted.
- At 375 × 668, teacher and student forms remain scrollable and their final controls lie within the scrollable document. Login/recovery controls remain accessible, with the logo visible.
- Password visibility toggling and Login → role selection → teacher signup / Login → recovery navigation were checked. Empty registration validation stays on the first step.
- No browser console warnings/errors were captured in the final check.

Evidence is outside the repository at:

`C:/Users/iamdo/.codex/visualizations/2026/10/22/01a16113-8044-7d92-beda-6242b47e3b4d/auth-background-qa/`

Key screenshots: `standardized-auth-backgrounds.jpg`, `mobile-contact-sheet.jpg`, `states-contact-sheet.jpg`, `after-login-1440.jpg`, `teacher-step-2-desktop.jpg`, `teacher-step-2-mobile.jpg`, `student-step-2-mobile.jpg`, `after-otp-1440.jpg`, `preview-reset-1440.jpg`, `preview-reset-success-1440.jpg`, and `preview-principal-1440.jpg`. JSON files contain baseline/final geometry, responsive measurements, template checks, source preservation, guards and pixel comparison evidence.

## 8. Checks and tests performed

- `python pabasa_site/manage.py check`: no issues.
- `python pabasa_site/manage.py test pabasa_app.tests_otp_debug pabasa_app.tests.TeacherSignupTemplateTests pabasa_app.tests.StudentSignupTemplateTests pabasa_app.tests_static_images --verbosity 1`: **49 tests ran; 48 passed and 1 failed**.
- All 21 OTP/recovery tests passed, including normal verification, expiration/session binding and completion workflows in an isolated test database. Email helpers are mocked by that suite; no real recovery messages were sent.
- All 25 static-image tests passed. Teacher signup’s template test and one student-template test also passed.
- The failing test is `StudentSignupTemplateTests.test_student_signup_template_includes_privacy_step_and_consent_controls`. It expects the old literal `Step ${currentStep + 1} of ${steps.length}`. That string is already absent from the saved pre-change template, which uses `${stepLabels[currentStep]} ${currentStep + 1}/${steps.length}`. This mismatch predates the background work; neither the test nor the approved form wording was changed.
- Test setup emitted an existing naive-datetime warning from `Material.created_at`; no model or migration was changed.
- Seven isolated error/protected/success template renders contain exactly one approved image reference, no stock image and the authentication body class.
- Static finders resolve the original PNG.
- Both protected routes still redirect anonymous requests: password reset to `/forgot-password/`, and principal temporary-password change to `/auth/`. This was checked with Django’s client and in the browser.
- All eight form/script source comparisons and protected-file hash comparisons passed.

## 9. Remaining limitations

No real login, incorrect-credentials submission, account creation, OTP request/resend or password change was performed in the browser. Later registration/OTP/completion panels were audited in their original shared page structure rather than reached by submitting registration. Protected reset/principal and confirmation screens were visually checked as existing Django template previews, not as authenticated end-to-end workflows. Their actual access guards remain intact.

The browser checks used the available Chromium-based in-app browser, not real mobile devices or other browser engines. Exact 1366px coverage is bracketed as noted above. The single pre-existing student-template test failure remains unresolved because changing form wording/tests is outside this background-only scope. The original 2.14 MiB PNG remains unchanged.

## 10. Deployment status

Local implementation only. No deployment, backend change, schema change, authentication/security change, or real account/recovery submission was made. The temporary read-only preview server was stopped after verification. The normal local Django server remains the implementation target.
