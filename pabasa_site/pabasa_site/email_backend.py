"""SMTP delivery with a separately authenticated backup sender."""

from copy import copy
import logging
import smtplib
import threading

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


logger = logging.getLogger(__name__)
REJECTED_MESSAGE = (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused)


class FallbackSMTPBackend(BaseEmailBackend):
    """Retry connection failures and explicit SMTP rejections with Gmail.

    A disconnect during message submission has an uncertain delivery outcome
    and is not retried automatically. Never resend an accepted message because
    of a failure while closing its connection.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.primary = SMTPBackend(fail_silently=False, **kwargs)
        self.backup = None
        if settings.EMAIL_BACKUP_HOST_PASSWORD:
            self.backup = SMTPBackend(
                host=settings.EMAIL_BACKUP_HOST,
                port=587,
                username=settings.EMAIL_BACKUP_HOST_USER,
                password=settings.EMAIL_BACKUP_HOST_PASSWORD,
                use_tls=True,
                use_ssl=False,
                timeout=settings.EMAIL_TIMEOUT,
                fail_silently=False,
            )
        self._lock = threading.RLock()

    def _send_primary(self, message):
        # Open separately so connection errors can be distinguished from
        # ambiguous errors during DATA. An already-open Django connection is
        # retained by send_messages(), allowing cleanup after counting success.
        try:
            self.primary.open()
        except OSError:
            if self.backup is None:
                raise
            return None
        try:
            return self.primary.send_messages([message])
        except REJECTED_MESSAGE:
            if self.backup is None:
                raise
            return None

    def _send_backup(self, message):
        backup_message = copy(message)
        backup_message.from_email = settings.EMAIL_BACKUP_FROM_EMAIL
        # EmailMessage headers can override from_email. Use the authenticated
        # backup sender in both the envelope and visible From header.
        backup_message.extra_headers = {
            name: value for name, value in message.extra_headers.items()
            if name.lower() not in {'from', 'sender'}
        }
        self.backup.open()
        return self.backup.send_messages([backup_message])

    def close(self):
        with self._lock:
            for backend in (self.primary, self.backup):
                if backend is not None:
                    try:
                        backend.close()
                    except OSError:
                        # Do not log SMTP responses: they can contain addresses
                        # or other sensitive values.
                        logger.warning('SMTP connection cleanup failed.')

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        with self._lock:
            num_sent = 0
            use_backup = False
            try:
                for message in email_messages:
                    if not message.recipients():
                        continue
                    try:
                        sent = None if use_backup else self._send_primary(message)
                        if sent is None:
                            if not use_backup:
                                logger.warning('Primary SMTP unavailable; using backup SMTP.')
                            use_backup = True
                            sent = self._send_backup(message)
                        num_sent += sent
                    except OSError:
                        # An interrupted login or DATA transaction must not
                        # leave a partial connection for the next message.
                        self.close()
                        if not self.fail_silently:
                            raise
                        logger.warning('SMTP message delivery failed.')
                return num_sent
            finally:
                self.close()
