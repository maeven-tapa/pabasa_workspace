"""Bounded, shadow-mode acoustic measurements for prescribed reading."""
from __future__ import annotations
import io, math, struct
from dataclasses import asdict, dataclass
import av

MAX_BYTES = 20 * 1024 * 1024
MAX_DURATION_SECONDS = 120.0
TARGET_RATE = 16_000
FRAME_SECONDS = 0.02
MIN_SEGMENT_SECONDS = 0.04
MIN_CANDIDATE_PAUSE_SECONDS = 0.12

class AudioAnalysisError(ValueError):
    """Expected, non-fatal failure while decoding or measuring a recording."""

@dataclass(frozen=True)
class AudioFeatures:
    duration_seconds: float; sample_rate: int; channels: int; sample_count: int
    speech_activity_ratio: float; speech_duration_seconds: float
    speech_start_seconds: float | None; speech_end_seconds: float | None
    speech_segments: list; internal_silence_segments: list
    candidate_hesitation_pauses: list; speech_continuity_ratio: float
    possible_restart_count: int | None; repetition_evidence: str
    rms: float; peak: float; quality: str; content_type: str
    analysis_version: str = "shadow-2"
    def as_dict(self): return asdict(self)

def _pcm_samples(frame):
    if not frame.planes: return []
    raw = bytes(frame.planes[0]); usable = len(raw) - (len(raw) % 2)
    return [value[0] for value in struct.iter_unpack("<h", raw[:usable])]

def content_type_for_item(item_index):
    if item_index is not None and 0 <= int(item_index) <= 6: return "word"
    if item_index is not None and 7 <= int(item_index) <= 16: return "phrase"
    if item_index is not None and 17 <= int(item_index) <= 21: return "sentence"
    return "unknown"

def _segments(active):
    result = []; start = None
    for index, is_active in enumerate(active + [False]):
        if is_active and start is None: start = index
        if not is_active and start is not None:
            end = index
            if (end - start) * FRAME_SECONDS >= MIN_SEGMENT_SECONDS:
                result.append({'start_seconds': round(start * FRAME_SECONDS, 3), 'end_seconds': round(end * FRAME_SECONDS, 3), 'duration_seconds': round((end - start) * FRAME_SECONDS, 3)})
            start = None
    return result

def _silences(active):
    result = []; start = None
    for index, is_active in enumerate(active + [True]):
        if not is_active and start is None: start = index
        if is_active and start is not None:
            end = index
            position = 'leading' if not any(active[:start]) else ('trailing' if not any(active[end:]) else 'internal')
            result.append({'start_seconds': round(start * FRAME_SECONDS, 3), 'end_seconds': round(end * FRAME_SECONDS, 3), 'duration_seconds': round((end - start) * FRAME_SECONDS, 3), 'position': position})
            start = None
    return result

def extract_audio_features(data: bytes, *, mime_type: str = "", item_index=None) -> dict:
    if not data: raise AudioAnalysisError("empty_audio")
    if len(data) > MAX_BYTES: raise AudioAnalysisError("audio_too_large")
    samples = []
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None: raise AudioAnalysisError("no_audio_stream")
            resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=TARGET_RATE)
            for frame in container.decode(stream):
                for converted in resampler.resample(frame):
                    samples.extend(_pcm_samples(converted))
                    if len(samples) / TARGET_RATE > MAX_DURATION_SECONDS: raise AudioAnalysisError("audio_too_long")
    except AudioAnalysisError: raise
    except Exception as exc: raise AudioAnalysisError("audio_decode_failed") from exc
    if not samples: raise AudioAnalysisError("no_samples")
    frame_size = max(1, int(TARGET_RATE * FRAME_SECONDS)); energies = []; peak = 0
    for start in range(0, len(samples), frame_size):
        chunk = samples[start:start + frame_size]
        energies.append(math.sqrt(sum(sample * sample for sample in chunk) / len(chunk)) / 32768.0)
        peak = max(peak, max(abs(sample) for sample in chunk) / 32768.0)
    noise_floor = max(0.008, min(0.04, sorted(energies)[max(0, len(energies) // 10)]))
    active = [energy > noise_floor for energy in energies]
    segments = _segments(active); silences = _silences(active)
    internal = [s for s in silences if s['position'] == 'internal']
    candidates = [s for s in internal if s['duration_seconds'] >= MIN_CANDIDATE_PAUSE_SECONDS]
    speech_duration = sum(s['duration_seconds'] for s in segments)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768.0
    return AudioFeatures(round(len(samples) / TARGET_RATE, 3), TARGET_RATE, 1, len(samples), round(sum(active) / len(active), 4), round(speech_duration, 3), segments[0]['start_seconds'] if segments else None, segments[-1]['end_seconds'] if segments else None, segments, internal, candidates, round(1 / len(segments), 4) if segments else 0.0, None, 'not_inferable_from_energy', round(rms, 6), round(peak, 6), 'usable' if peak >= 0.01 and rms >= 0.003 else 'low_signal', content_type_for_item(item_index)).as_dict()
