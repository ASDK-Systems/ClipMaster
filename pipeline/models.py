"""
YTAutomation — Shared data models for the pipeline.

These Pydantic models flow between pipeline stages.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Metadata extracted during download."""

    url: str
    video_id: str
    title: str
    channel: str
    duration_seconds: float
    thumbnail_url: str = ""
    description: str = ""
    upload_date: str = ""
    file_path: str = ""


class TranscriptSegment(BaseModel):
    """A single segment from speech-to-text."""

    start: float  # seconds
    end: float  # seconds
    text: str


class TranscriptWord(BaseModel):
    """A single word with precise timestamps."""

    start: float
    end: float
    word: str


class Transcript(BaseModel):
    """Full transcript with segments and optional word-level detail."""

    language: str = "en"
    segments: list[TranscriptSegment] = Field(default_factory=list)
    words: list[TranscriptWord] = Field(default_factory=list)
    full_text: str = ""


class ViralClip(BaseModel):
    """A viral clip candidate identified by AI."""

    start: float  # seconds
    end: float  # seconds
    title: str
    hook_description: str = ""
    virality_score: float = Field(ge=0, le=10)
    reasoning: str = ""
    duration: float = 0.0

    def model_post_init(self, __context: object) -> None:
        if self.duration == 0.0:
            self.duration = self.end - self.start


class ClipResult(BaseModel):
    """Result of clipping + processing a single viral clip."""

    clip_index: int
    viral_clip: ViralClip
    clip_file_path: str = ""
    subtitled_file_path: str = ""
    subtitle_file_path: str = ""
    transcript: Transcript | None = None


class PipelineResult(BaseModel):
    """Final output of the entire pipeline."""

    video_metadata: VideoMetadata
    full_transcript: Transcript
    viral_clips_detected: list[ViralClip] = Field(default_factory=list)
    clip_results: list[ClipResult] = Field(default_factory=list)
    status: str = "completed"
    error: str | None = None
