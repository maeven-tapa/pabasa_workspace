# OTP debug switch

In **Admin → Settings → OTP Debug**, check **Disable OTP** and select
**Save OTP Debug Setting**. Uncheck it and save to restore OTP verification.
The switch is off by default and applies across the application immediately.
Only an active admin account can save it; changes appear in the activity log.

When on, teacher and student signups complete without sending or entering an
OTP, and password recovery proceeds directly to the reset-password form.
Pending OTP forms can also complete while debugging is enabled. Signup
validation, account IDs, school/class assignment, enrollment, password checks,
confirmation emails, and notifications continue through their existing logic.
The switch does not disable other emails or change login behavior.

Teacher and student signup require email while OTP verification is enabled.
When this debug switch is on, email becomes optional and new students receive
the default password `12345678`. With the switch off, students choose their own
password and complete email OTP verification. Teachers choose their own
password in both modes. See `REGISTRATION_DEFAULTS.md` for the signup behavior.

**Use only for debugging:** while on, anyone who knows an account's email
address can reset that account's password without proving ownership of the
address. Restore OTP when debugging is finished. Password-reset sessions that
bypassed OTP are rejected if the switch is turned off before completion;
sessions verified with a real OTP continue normally.

The additive migration `0030_otp_debug_settings` must be applied before using
this version. It creates a singleton settings table with `disable_otp=False`;
it does not change existing account or assessment tables. Follow the repository
migration-readiness and backup requirements for local or Cloud Run releases.

Regression coverage is in `pabasa_app.tests_otp_debug`, alongside the existing
signup, class architecture, and email backend tests.

## Local validation — October 13, 2026

- All 45 focused OTP, automatic-enrollment, teacher-assignment, and email-backend
  tests passed. Django system checks and `migrate --check` passed.
- Browser checks passed for the desktop and mobile settings switch, teacher and
  student signup completion without OTP, password reset without OTP, and the
  normal signup OTP screen after disabling debugging. No JavaScript errors were
  observed. Checks used a separate database with synthetic accounts and captured
  emails; the test server was stopped and its database removed afterward.
- The broader regression run found 26 failures/errors in existing tests. All
  26 also occur against the original source. They were left outside this change.
- `makemigrations --check --dry-run` still reports 29 existing ID-field changes
  from AutoField to BigAutoField. Removing the OTP model from both compared
  states produces exactly the same differences; the OTP model matches its
  migration. These unrelated schema changes were not added to the release.
- The intended local SQLite database passed migration readiness, was backed
  up, and received only migration `0030_otp_debug_settings`. OTP debugging is
  off locally. This change has not been deployed to Cloud Run.
