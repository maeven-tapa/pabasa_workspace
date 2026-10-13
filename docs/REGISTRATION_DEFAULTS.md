# Optional signup email and initial passwords

The Admin OTP Debug switch controls signup requirements:

| OTP verification | Email | New student password |
| --- | --- | --- |
| Enabled (Disable OTP off) | Required | Student chooses and confirms a password |
| Disabled (Disable OTP on) | Optional | `12345678`, stored as a hash |

Students who supply email with OTP enabled must complete verification before
account creation. Omitting email cannot bypass verification. Student signup's
Account step and completion screen show the initial password only when OTP is
disabled. Students created in Django admin also receive the default only while
OTP is disabled; otherwise their email and password hash are required.

**The default password remains limited to new students.** Teachers require
email with OTP enabled, can omit email with OTP disabled, and choose their own
password in both modes. Principal accounts
keep their surname-based temporary password and required first-login password
change. Other roles do not receive the student default password.

Existing passwords remain unchanged. Normal password changes, forgotten
password recovery, and administrator resets of existing principal passwords
keep their existing behavior. Historical account imports retain their saved
password hashes.

When OTP is disabled and signup email is omitted or blank, the account stores
`NULL` and completes without email OTP or confirmation email. Multiple accounts
can omit email in this mode. Supplied addresses must remain valid and unique.
Account IDs, school/class assignment,
enrollment, and notifications still use the existing completion logic.

An account without email logs in with its generated PABASA ID and can change
its password in Settings. Email-based password recovery needs a saved email.
The profile can be edited while its email remains absent; adding an email
still uses the existing email-verification flow.

Migration `0031_optional_email_default_password` makes the unique email field
nullable. Migration `0032_student_only_default_password` removes the former
generic password-field default so it is only applied when creating a student
account. Neither migration resets existing passwords. Follow the
migration-readiness and backup steps before applying them. The conditional
signup-policy correction needs no additional schema migration.

If an admin changes OTP while a signup form is open, the server rejects that
stale submission, the form updates its requirements, and the user reviews and
submits again. A pending student signup completed after OTP is disabled uses
the default password; already-created accounts are not modified.

## Local validation — October 13, 2026

- 85 focused tests passed across the full run and the registration-module
  rerun, covering conditional signup requirements, stale forms, the student-only default password,
  teacher-selected and principal temporary passwords, registration, OTP debugging,
  enrollment, teacher assignment, email delivery, account sessions, and
  principal-form validation.
- The additional principal report isolation test still fails with the same
  result against the original source. The existing student dashboard also
  reproduces `sessions.filter is not a function` against original source.
  Both are outside this registration change.
- Schema checks still report the same 29 pre-existing ID-field differences
  documented in `OTP_DEBUG_SWITCH.md`; the new model fields match migration
  `0031_optional_email_default_password`.
- Browser checks passed on desktop and mobile for required email and chosen
  password with OTP enabled, optional email and default student password with
  OTP disabled, teacher password selection, verification, login, and stale-form
  recovery after toggling in either direction. Password panels were visually
  verified at full width in both modes. Temporary test
  servers were stopped and their synthetic-account database was removed.
- The local SQLite database was backed up before migrations `0031` and `0032`. Every
  existing account's email and password hash matched its pre-migration value.
  The local server was restarted at `http://127.0.0.1:8000`; this change has not
  been deployed to Cloud Run.
