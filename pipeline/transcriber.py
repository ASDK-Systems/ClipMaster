"""
YTAutomation — Speech-to-Text Module

Transcribes video/audio using OpenAI's cloud Whisper API (cross-platform).
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI
from config import settings
from pipeline.models import Transcript, TranscriptSegment, TranscriptWord

logger = logging.getLogger(__name__)

class TranscriptionError(Exception):
    """Raised when transcription fails."""


def _extract_audio(video_path: str, output_path: str, on_progress: callable = None) -> str:
    """
    Extract audio from video file using FFmpeg.
    Converts to mono MP3 at 16kHz (optimal for Whisper).
    """
    logger.info("Extracting audio from: %s", video_path)
    if on_progress:
        on_progress("TRANSCRIBE", f"Extracting audio to {output_path}...")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",                   # No video
        "-acodec", "libmp3lame", # MP3 codec
        "-ar", "16000",          # 16kHz sample rate (Whisper optimal)
        "-ac", "1",              # Mono
        "-b:a", "64k",           # Low bitrate to keep size down
        "-y",                    # Overwrite
        output_path,
    ]

    if settings.ffmpeg_location:
        cmd[0] = settings.ffmpeg_location

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TranscriptionError(f"FFmpeg audio extraction failed: {result.stderr}")

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    if on_progress:
        on_progress("TRANSCRIBE", f"Audio extracted: {file_size_mb:.1f} MB. Sending to OpenAI Whisper...")
    logger.info("Audio extracted: %.1f MB", file_size_mb)

    return output_path


def transcribe_audio(
    audio_path: str,
    language: str | None = None,
    on_progress: callable = None,
) -> Transcript:
    """
    Transcribe an audio file using OpenAI's cloud Whisper API.
    """
    if not settings.openai_api_key:
        raise TranscriptionError(
            "OPENAI_API_KEY not set. Required for transcription (cloud Whisper API)."
        )

    logger.info("Transcribing via OpenAI Whisper API")
    if on_progress:
        on_progress("TRANSCRIBE", "Uploading audio to OpenAI Whisper API...")

    client = OpenAI(api_key=settings.openai_api_key)

    kwargs = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment", "word"],
    }
    if language:
        kwargs["language"] = language

    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(file=audio_file, **kwargs)

    result = result.model_dump()

    all_segments: list[TranscriptSegment] = []
    all_words: list[TranscriptWord] = []

    detected_language = result.get("language", language or "en")

    for seg in result.get("segments", []):
        all_segments.append(
            TranscriptSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip(),
            )
        )

    # OpenAI returns word timestamps as a flat top-level list, not nested per-segment
    for word_data in result.get("words", []):
        all_words.append(
            TranscriptWord(
                start=word_data["start"],
                end=word_data["end"],
                word=word_data["word"].strip(),
            )
        )

    transcript = Transcript(
        language=detected_language,
        segments=all_segments,
        words=all_words,
        full_text=result.get("text", "").strip(),
    )

    msg = f"Transcription complete: {len(transcript.segments)} segments, {len(transcript.words)} words, language={transcript.language}"
    logger.info(msg)
    if on_progress:
        on_progress("TRANSCRIBE", msg)

    return transcript


def transcribe_video(
    video_path: str,
    language: str | None = None,
    on_progress: callable = None,
) -> Transcript:
    """
    Full pipeline: extract audio from video, then transcribe.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = str(Path(tmp_dir) / "audio.mp3")
        _extract_audio(video_path, audio_path, on_progress)
        return transcribe_audio(audio_path, language=language, on_progress=on_progress)
