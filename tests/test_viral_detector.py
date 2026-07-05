"""
Tests for the viral_detector module.
"""

import pytest

from pipeline.models import Transcript, TranscriptSegment, VideoMetadata
from pipeline.viral_detector import (
    ViralDetectionError,
    _format_transcript_for_prompt,
    _parse_ai_response,
    _seconds_to_timestamp,
    _validate_clips,
)


class TestSecondsToTimestamp:
    def test_minutes_seconds(self):
        assert _seconds_to_timestamp(90) == "01:30"

    def test_hours(self):
        assert _seconds_to_timestamp(3661) == "01:01:01"

    def test_zero(self):
        assert _seconds_to_timestamp(0) == "00:00"


class TestParseAiResponse:
    def test_valid_json_array(self):
        response = '[{"start": 10, "end": 50, "title": "Test"}]'
        result = _parse_ai_response(response)
        assert len(result) == 1
        assert result[0]["start"] == 10

    def test_markdown_wrapped_json(self):
        response = '```json\n[{"start": 10, "end": 50}]\n```'
        result = _parse_ai_response(response)
        assert len(result) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ViralDetectionError, match="invalid JSON"):
            _parse_ai_response("this is not json")

    def test_non_array_raises(self):
        with pytest.raises(ViralDetectionError, match="not a JSON array"):
            _parse_ai_response('{"key": "value"}')


class TestValidateClips:
    def test_valid_clips(self):
        raw = [
            {
                "start": 10.0,
                "end": 50.0,
                "title": "Clip 1",
                "virality_score": 8.5,
            }
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert len(clips) == 1
        assert clips[0].title == "Clip 1"

    def test_clips_sorted_by_score(self):
        raw = [
            {"start": 10, "end": 50, "title": "Low", "virality_score": 3},
            {"start": 100, "end": 150, "title": "High", "virality_score": 9},
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert clips[0].title == "High"
        assert clips[1].title == "Low"

    def test_clips_clamped_to_duration(self):
        raw = [
            {"start": 580, "end": 700, "title": "Overflow", "virality_score": 5},
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert len(clips) == 1
        assert clips[0].end <= 600.0

    def test_too_short_clips_filtered(self):
        raw = [
            {"start": 10, "end": 15, "title": "Tiny", "virality_score": 5},
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert len(clips) == 0  # 5 seconds is too short

    def test_too_long_clips_trimmed(self):
        raw = [
            {"start": 10, "end": 200, "title": "Long", "virality_score": 5},
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert len(clips) == 1
        assert clips[0].duration <= 90  # Trimmed to 90s

    def test_invalid_timestamps_skipped(self):
        raw = [
            {"start": 50, "end": 30, "title": "Reversed", "virality_score": 5},
        ]
        clips = _validate_clips(raw, video_duration=600.0)
        assert len(clips) == 0


class TestFormatTranscript:
    def test_formats_with_timestamps(self):
        transcript = Transcript(
            segments=[
                TranscriptSegment(start=0, end=5, text="Hello world"),
                TranscriptSegment(start=5, end=10, text="How are you"),
            ]
        )
        result = _format_transcript_for_prompt(transcript)
        assert "[00:00] Hello world" in result
        assert "[00:05] How are you" in result

    def test_truncation(self):
        segments = [
            TranscriptSegment(start=i, end=i + 1, text=f"Word {i}" * 100)
            for i in range(1000)
        ]
        transcript = Transcript(segments=segments)
        result = _format_transcript_for_prompt(transcript, max_chars=1000)
        assert "truncated" in result
