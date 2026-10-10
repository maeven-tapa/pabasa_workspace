# Brevo email setup

Prepared October 10, 2026 (Asia/Manila). Deployment status must be verified
against Cloud Run; this document is not evidence of an activated release.

PABASA uses `pabasa_site.email_backend.FallbackSMTPBackend` for OTPs,
confirmations, and notifications. The primary SMTP host, login, and sender are
configurable with environment variables. Without overrides, the existing Gmail
settings remain the defaults. Both connections use port 587 with STARTTLS and a
15-second connection timeout. Gmail fallback is enabled only when its separate
password is configured.

## Account and secret preparation

1. Authenticate `tupcpabasa.app` in Brevo using the DNS records shown in the
   account, and add sender `PABASA <noreply@tupcpabasa.app>`.
2. Generate an SMTP key (not an API key). Replace any key exposed in chat or
   screenshots. Do not put the key in source code, logs, command arguments,
   or this document.
3. Store the key as a version of Google Secret Manager secret
   `brevo_emailpass`, project `project-2b0d295d-ee06-40a7-927`. The user
   selected this secret after the empty `pabasa-brevo-smtp-key` placeholder
   was created. The placeholder is not used by the release.
4. Grant `roles/secretmanager.secretAccessor` on that secret to
   `pabasa@project-2b0d295d-ee06-40a7-927.iam.gserviceaccount.com`.
5. If Brevo reports that transactional sending is not activated, request
   activation through Brevo support.

## Intended Cloud Run configuration

| Environment variable | Value or secret reference |
| --- | --- |
| `EMAIL_HOST` | `smtp-relay.brevo.com` |
| `EMAIL_HOST_USER` | SMTP login from Brevo's SMTP settings page |
| `DEFAULT_FROM_EMAIL` | `PABASA <noreply@tupcpabasa.app>` |
| `EMAIL_HOST_PASSWORD` | `brevo_emailpass:<numeric version>` |
| `EMAIL_BACKUP_HOST` | `smtp.gmail.com` |
| `EMAIL_BACKUP_HOST_USER` | `pabasa.tupc@gmail.com` |
| `EMAIL_BACKUP_FROM_EMAIL` | `PABASA <pabasa.tupc@gmail.com>` |
| `EMAIL_BACKUP_HOST_PASSWORD` | `pabasa_apppassword:<numeric version>` |

The SMTP login is a technical identifier, not the sender email. Use the exact
login displayed by Brevo. Pin the secret version so a credential change does
not silently affect a running release. Retain the existing Gmail secret
`pabasa_apppassword` for Gmail fallback and traffic rollback to the previous
release. Do not overwrite the Gmail secret with the Brevo key. Neither email
password should be assigned to `DJANGO_SECRET_KEY`.

Both `brevo_emailpass` version 1 and `pabasa_apppassword` version 1 passed
STARTTLS SMTP authentication before the push. This check did not send email
and does not establish inbox delivery. No credential values were recorded.

## Fallback behavior

Brevo is attempted first. A connection or authentication failure before message
submission, or an explicit SMTP rejection, retries that message through Gmail.
The backup uses its own Gmail sender while preserving recipients, message
content, HTML, attachments, and Reply-To. The original email object is preserved.
After a primary failure in a batch, the remaining messages use Gmail; previously
accepted messages are not resent.

A timeout or disconnect during message submission has an uncertain delivery
outcome, so it raises instead of automatically retrying. Errors while closing a
connection after acceptance do not cause resend. If both providers fail, the
backend raises unless the caller explicitly requests `fail_silently=True`, in
which case unsuccessful messages are not counted as sent. Logs do not include
SMTP response bodies, credentials, OTPs, or recipient addresses.

Fallback cannot detect later bounces, spam filtering, or emails accepted into
Brevo's queue. Reaching the daily limit does not guarantee immediate Gmail
fallback: an SMTP rejection triggers fallback, but SMTP acceptance into a queue
does not.

Deploy an image containing the configurable settings. Follow the repository's
Cloud Run migration job and readiness requirements, using the same image digest
and database identity for the job and web service. Keep the new revision off
production traffic until startup and email delivery are verified. Do not
replace `DJANGO_SECRET_KEY` with the SMTP key.

Verify a test email to an authorized recipient, an OTP and resend workflow,
sender/authentication headers in the received message, Brevo delivery logs,
and Cloud Run errors before switching traffic. SMTP acceptance alone does not
prove inbox delivery.

Local transport tests (mock SMTP, no external messages) cover primary success,
connection/authentication failures, explicit rejection, sender rewriting,
message preservation, batch handling, ambiguous delivery, cleanup failure,
both-provider failure, silent failure, and the three OTP email helpers. Run:

```powershell
.\.venv\Scripts\python.exe pabasa_site/manage.py test pabasa_app.tests_email_backend --noinput
.\.venv\Scripts\python.exe pabasa_site/manage.py check
```

Brevo's free allowance is 300 emails per day, shared by OTPs, resends,
confirmations, and other messages. Messages queued after reaching the allowance
can arrive after PABASA's 10-minute OTP expiry.

References:

- [Brevo SMTP setup](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP)
- [Brevo domain authentication](https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC)
- [Brevo SMTP troubleshooting](https://help.brevo.com/hc/en-us/articles/115000188150-Troubleshooting-Issues-with-Brevo-SMTP)
- [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
