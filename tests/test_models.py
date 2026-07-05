"""
Tests for the pipeline models.
"""

from pipeline.models import (
    ClipResult,
    PipelineResult,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    VideoMetadata,
    ViralClip,
)


def test_video_metadata():
    meta = VideoMetadata(
        url="https://www.youtube.com/watch?v=test123",
        video_id="test123",
        title="Test Video",
        channel="Test Channel",
        duration_seconds=600.0,
    )
    assert meta.video_id == "test123"
    assert meta.duration_seconds == 600.0


def test_transcript_segment():
    seg = TranscriptSegment(start=10.5, end=15.3, text="Hello world")
    assert seg.start == 10.5
    assert seg.end == 15.3
    assert seg.text == "Hello world"


def test_transcript_word():
    word = TranscriptWord(start=10.5, end=11.0, word="Hello")
    assert word.word == "Hello"


def test_transcript():
    transcript = Transcript(
        language="en",
        segments=[
            TranscriptSegment(start=0, end=5, text="Hello"),
            TranscriptSegment(start=5, end=10, text="World"),
        ],
        words=[
            TranscriptWord(start=0, end=2, word="Hello"),
            TranscriptWord(start=5, end=7, word="World"),
        ],
        full_text="Hello World",
    )
    assert len(transcript.segments) == 2
    assert len(transcript.words) == 2
    assert transcript.language == "en"


def test_viral_clip_duration_auto_calculated():
    clip = ViralClip(
        start=100.0,
        end=160.0,
        title="Test Clip",
        virality_score=8.5,
    )
    assert clip.duration == 60.0


def test_viral_clip_score_bounds():
    clip = ViralClip(
        start=0,
        end=30,
        title="Test",
        virality_score=8.0,
    )
    assert 0 <= clip.virality_score <= 10


def test_clip_result():
    vc = ViralClip(start=10, end=50, title="Clip 1", virality_score=7.0)
    result = ClipResult(
        clip_index=0,
        viral_clip=vc,
        clip_file_path="/tmp/clip_00.mp4",
        subtitled_file_path="/tmp/clip_00_subtitled.mp4",
    )
    assert result.clip_index == 0
    assert result.clip_file_path == "/tmp/clip_00.mp4"


def test_pipeline_result():
    meta = VideoMetadata(
        url="https://youtu.be/test",
        video_id="test",
        title="Test",
        channel="Ch",
        duration_seconds=300,
    )
    transcript = Transcript(full_text="Hello world")
    result = PipelineResult(
        video_metadata=meta,
        full_transcript=transcript,
        status="completed",
    )
    assert result.status == "completed"
    assert len(result.clip_results) == 0
