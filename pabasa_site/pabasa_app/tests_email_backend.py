"""Verify failover through Django's real SMTP backend without network access."""

import smtplib
from unittest.mock import MagicMock, patch

from django.core.mail import EmailMultiAlternatives, get_connection
from django.test import RequestFactory, SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND='pabasa_site.email_backend.FallbackSMTPBackend',
    EMAIL_HOST='smtp-relay.brevo.com',
    EMAIL_HOST_USER='test@smtp-brevo.com',
    EMAIL_HOST_PASSWORD='test-only-primary-key',
    DEFAULT_FROM_EMAIL='PABASA <noreply@example.com>',
    EMAIL_BACKUP_HOST='smtp.gmail.com',
    EMAIL_BACKUP_HOST_USER='backup@example.com',
    EMAIL_BACKUP_HOST_PASSWORD='test-only-backup-password',
    EMAIL_BACKUP_FROM_EMAIL='PABASA <backup@example.com>',
    EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_TIMEOUT=15,
)
class FallbackSMTPBackendTests(SimpleTestCase):
    def setUp(self):
        self.primary = MagicMock()
        self.backup = MagicMock()
        self.primary.sendmail.return_value = {}
        self.backup.sendmail.return_value = {}
        self.smtp_patch = patch(
            'django.core.mail.backends.smtp.smtplib.SMTP',
            side_effect=[self.primary, self.backup],
        )
        self.smtp = self.smtp_patch.start()
        self.addCleanup(self.smtp_patch.stop)

    def message(self, subject='OTP'):
        message = EmailMultiAlternatives(subject, 'Test message', to=['reader@example.com'])
        message.attach_alternative('<p>Test message</p>', 'text/html')
        return message

    def test_primary_success_does_not_contact_backup(self):
        self.assertEqual(self.message().send(), 1)
        self.assertEqual(self.smtp.call_count, 1)
        self.primary.starttls.assert_called_once()
        self.primary.login.assert_called_once_with('test@smtp-brevo.com', 'test-only-primary-key')
        self.backup.sendmail.assert_not_called()

    def test_connection_failure_uses_backup(self):
        self.smtp.side_effect = [TimeoutError('connection timed out'), self.backup]
        self.assertEqual(self.message().send(), 1)
        self.backup.login.assert_called_once_with('backup@example.com', 'test-only-backup-password')
        self.backup.starttls.assert_called_once()

    def test_authentication_failure_uses_backup(self):
        self.primary.login.side_effect = smtplib.SMTPAuthenticationError(535, b'rejected')
        self.assertEqual(self.message().send(), 1)
        self.backup.sendmail.assert_called_once()

    def test_explicit_rejection_uses_backup_and_preserves_message(self):
        self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'quota exceeded')
        message = self.message()
        message.extra_headers = {'From': 'noreply@example.com', 'X-Test': 'preserved'}
        message.reply_to = ['help@example.com']
        message.attach('test.txt', 'attachment', 'text/plain')
        self.assertEqual(message.send(), 1)
        sender, recipients, payload = self.backup.sendmail.call_args.args
        self.assertEqual(sender, 'backup@example.com')
        self.assertEqual(recipients, ['reader@example.com'])
        self.assertIn(b'From: PABASA <backup@example.com>', payload)
        self.assertIn(b'Reply-To: help@example.com', payload)
        self.assertIn(b'X-Test: preserved', payload)
        self.assertIn(b'text/html', payload)
        self.assertIn(b'test.txt', payload)
        self.assertEqual(message.from_email, 'PABASA <noreply@example.com>')
        self.assertEqual(message.extra_headers['From'], 'noreply@example.com')

    def test_recipient_rejection_uses_backup(self):
        self.primary.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {'reader@example.com': (450, b'rejected')}
        )
        self.assertEqual(self.message().send(), 1)
        self.backup.sendmail.assert_called_once()

    def test_all_otp_email_helpers_use_backup_on_primary_rejection(self):
        from pabasa_app import views

        request = RequestFactory().get('/', HTTP_HOST='localhost')
        for helper in (
            views.send_teacher_signup_otp_email,
            views.send_student_signup_otp_email,
            views.send_password_reset_otp_email,
        ):
            with self.subTest(helper=helper.__name__):
                self.smtp.side_effect = [self.primary, self.backup]
                self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'rejected')
                self.backup.sendmail.reset_mock()
                helper(request, 'reader@example.com', '123456', 'Test')
                self.backup.sendmail.assert_called_once()
                self.assertIn(b'123456', self.backup.sendmail.call_args.args[2])

    def test_batch_never_resends_already_accepted_messages(self):
        self.primary.sendmail.side_effect = [{}, smtplib.SMTPDataError(452, b'rejected')]
        messages = [self.message('First'), self.message('Second'), self.message('Third')]
        self.assertEqual(get_connection().send_messages(messages), 3)
        self.assertEqual(self.primary.sendmail.call_count, 2)
        self.assertEqual(self.backup.sendmail.call_count, 2)
        self.assertNotIn(b'Subject: First', self.backup.sendmail.call_args_list[0].args[2])
        self.assertEqual(self.smtp.call_count, 2)

    def test_uncertain_delivery_is_not_retried(self):
        for error in (TimeoutError('DATA timeout'), smtplib.SMTPServerDisconnected('disconnected')):
            with self.subTest(error=type(error).__name__):
                self.primary.sendmail.side_effect = error
                self.smtp.side_effect = [self.primary]
                with self.assertRaises(type(error)):
                    self.message().send()
                self.backup.sendmail.assert_not_called()

    def test_cleanup_failure_does_not_resend_accepted_message(self):
        self.primary.quit.side_effect = smtplib.SMTPResponseException(421, b'closing')
        self.assertEqual(self.message().send(), 1)
        self.backup.sendmail.assert_not_called()

    def test_both_providers_failing_raises(self):
        self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'rejected')
        self.backup.login.side_effect = smtplib.SMTPAuthenticationError(535, b'rejected')
        with self.assertRaises(smtplib.SMTPAuthenticationError):
            self.message().send()

    def test_fail_silently_still_attempts_backup_and_returns_zero_on_failure(self):
        self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'rejected')
        self.backup.sendmail.side_effect = smtplib.SMTPDataError(550, b'rejected')
        self.assertEqual(self.message().send(fail_silently=True), 0)
        self.backup.sendmail.assert_called_once()

    def test_silent_batch_failure_reconnects_backup_before_next_message(self):
        self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'rejected')
        recovered_backup = MagicMock()
        recovered_backup.sendmail.return_value = {}
        self.backup.login.side_effect = smtplib.SMTPAuthenticationError(535, b'rejected')
        self.smtp.side_effect = [self.primary, self.backup, recovered_backup]
        self.assertEqual(
            get_connection(fail_silently=True).send_messages([self.message(), self.message()]),
            1,
        )
        recovered_backup.login.assert_called_once_with(
            'backup@example.com', 'test-only-backup-password'
        )
        self.backup.sendmail.assert_not_called()

    def test_failure_logs_do_not_include_smtp_response_or_credentials(self):
        self.primary.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b'test-only-primary-key reader@example.com'
        )
        self.backup.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b'test-only-backup-password reader@example.com'
        )
        with self.assertLogs('pabasa_site.email_backend', level='WARNING') as captured:
            self.assertEqual(self.message().send(fail_silently=True), 0)
        output = '\n'.join(captured.output)
        self.assertNotIn('test-only-primary-key', output)
        self.assertNotIn('test-only-backup-password', output)
        self.assertNotIn('reader@example.com', output)

    @override_settings(EMAIL_BACKUP_HOST_PASSWORD='')
    def test_no_backup_secret_propagates_primary_failure(self):
        self.primary.sendmail.side_effect = smtplib.SMTPDataError(452, b'rejected')
        with self.assertRaises(smtplib.SMTPDataError):
            self.message().send()
        self.assertEqual(self.smtp.call_count, 1)

    def test_invalid_header_does_not_trigger_backup(self):
        message = self.message('invalid\nheader')
        with self.assertRaises(ValueError):
            message.send()
        self.backup.sendmail.assert_not_called()

    def test_empty_messages_do_not_open_connections(self):
        self.assertEqual(get_connection().send_messages([]), 0)
        message = self.message()
        message.to = []
        self.assertEqual(get_connection().send_messages([message]), 0)
        self.smtp.assert_not_called()
