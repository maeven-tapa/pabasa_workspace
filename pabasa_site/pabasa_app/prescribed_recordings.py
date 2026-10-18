"""Recording playback and optional analysis outside the upload transaction."""
import mimetypes

from django.db import connections
from django.http import FileResponse, HttpResponse

from .audio_fluency import AudioAnalysisError, extract_audio_features
from .models import PrescribedReadingAttempt, StudentActivityRecordingSubmission


def recording_response(audio_file):
    """Call only after the view has checked the teacher's recording access."""
    try:
        opened = audio_file.open('rb')
    except FileNotFoundError:
        return HttpResponse('This recording is unavailable. Please request a new recording.',status=404)
    response=FileResponse(opened,content_type=mimetypes.guess_type(audio_file.name)[0] or 'audio/webm')
    response['Content-Disposition']='inline'
    response['Cache-Control']='private, no-store'
    return response


def analyze_reading_attempt(attempt_id):
    """Best-effort shadow diagnostics; never change a learner's reading score."""
    attempt=PrescribedReadingAttempt.objects.filter(attempt_id=attempt_id).first()
    if not attempt:
        return
    # No request cleanup runs in this worker. Do not occupy its DB connection
    # while reading storage or decoding audio. The queue also closes on exit.
    connections.close_all()
    try:
        with attempt.audio_file.open('rb') as recording:
            audio=recording.read()
        features=extract_audio_features(audio,mime_type=attempt.audio_mime_type,item_index=attempt.item_index)
        status,error='complete',''
    except AudioAnalysisError as exc:
        features,status,error=None,'failed',str(exc)[:80]
    except Exception:
        features,status,error=None,'failed','analysis_failed'
    PrescribedReadingAttempt.objects.filter(pk=attempt.pk).update(
        audio_features=features,audio_analysis_status=status,audio_analysis_error=error,
        audio_analysis_version='shadow-1',
    )


def remove_replaced_recording(name):
    # Attempt history is immutable evidence. A replacement must retain files
    # still referenced by any recorded attempt or current submission.
    if (PrescribedReadingAttempt.objects.filter(audio_file=name).exists()
            or StudentActivityRecordingSubmission.objects.filter(audio_file=name).exists()):
        return
    connections.close_all()
    StudentActivityRecordingSubmission._meta.get_field('audio_file').storage.delete(name)
