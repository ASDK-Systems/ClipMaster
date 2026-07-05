"""
Tests for the clipper module.

Mocks FFmpeg subprocess calls to test logic without actual video files.
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.clipper import (
    ClipperError,
    clip_video,
    clip_viral_segments,
    get_video_duration,
    _get_ffmpeg_cmd,
    _get_ffprobe_cmd,
)
from pipeline.models import ViralClip


class TestGetFFmpegCmd:
    def test_default_returns_ffmpeg(self):
        with patch("pipeline.clipper.settings") as mock_settings:
            mock_settings.ffmpeg_location = None
            assert _get_ffmpeg_cmd() == "ffmpeg"

    def test_custom_location(self):
        with patch("pipeline.clipper.settings") as mock_settings:
            mock_settings.ffmpeg_location = "/opt/homebrew/bin/ffmpeg"
            assert _get_ffmpeg_cmd() == "/opt/homebrew/bin/ffmpeg"


class TestGetFFprobeCmd:
    def test_default_returns_ffprobe(self):
        with patch("pipeline.clipper.settings") as mock_settings:
            mock_settings.ffmpeg_location = None
            assert _get_ffprobe_cmd() == "ffprobe"

    def test_custom_location(self):
        with patch("pipeline.clipper.settings") as mock_settings:
            mock_settings.ffmpeg_location = "/opt/homebrew/bin/ffmpeg"
            result = _get_ffprobe_cmd()
            assert "ffprobe" in result
            assert "/opt/homebrew/bin/" in result


class TestGetVideoDuration:
    @patch("pipeline.clipper.subprocess.run")
    def test_returns_float_duration(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="123.456\n", stderr="")
        duration = get_video_duration("/tmp/test.mp4")
        assert duration == pytest.approx(123.456)

    @patch("pipeline.clipper.subprocess.run")
    def test_ffprobe_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with pytest.raises(ClipperError, match="ffprobe failed"):
            get_video_duration("/tmp/test.mp4")


class TestClipVideo:
    @patch("pipeline.clipper.subprocess.run")
    def test_negative_duration_raises(self, mock_run):
        """Clip with end < start should raise."""
        with pytest.raises(ClipperError, match="Invalid clip duration"):
            clip_video("/tmp/source.mp4", start=50.0, end=30.0, output_path="/tmp/out.mp4")

    @patch("pipeline.clipper.subprocess.run")
    def test_zero_duration_raises(self, mock_run):
        """Clip with start == end should raise."""
        with pytest.raises(ClipperError, match="Invalid clip duration"):
            clip_video("/tmp/source.mp4", start=30.0, end=30.0, output_path="/tmp/out.mp4")

    @patch("pipeline.clipper.subprocess.run")
    def test_ffmpeg_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="encoding error")
        with pytest.raises(ClipperError, match="FFmpeg clipping failed"):
            clip_video("/tmp/source.mp4", start=0.0, end=30.0, output_path="/tmp/out.mp4")

    @patch("pipeline.clipper.subprocess.run")
    def test_successful_clip(self, mock_run):
        """Test that a successful clip creates the file."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / "clip.mp4")
            # Simulate ffmpeg creating the file
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Create the output file to simulate ffmpeg success
            Path(output_path).write_text("fake video data")

            result = clip_video("/tmp/source.mp4", start=10.0, end=40.0, output_path=output_path)
            assert result == output_path

    @patch("pipeline.clipper.subprocess.run")
    def test_clip_output_not_created_raises(self, mock_run):
        """If ffmpeg returns 0 but file doesn't exist."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with pytest.raises(ClipperError, match="Clip was not created"):
            clip_video("/tmp/source.mp4", start=10.0, end=40.0, output_path="/tmp/nonexistent_output.mp4")

    @patch("pipeline.clipper.subprocess.run")
    def test_crop_vertical_adds_vf_filter(self, mock_run):
        """When crop_vertical is True, FFmpeg cmd should include -vf."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / "crop.mp4")
            Path(output_path).write_text("fake")
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            clip_video("/tmp/source.mp4", start=0.0, end=30.0, output_path=output_path, crop_vertical=True)

            # Check that ffmpeg was called with -vf
            call_args = mock_run.call_args[0][0]
            assert "-vf" in call_args
            vf_idx = call_args.index("-vf")
            assert "crop" in call_args[vf_idx + 1]


class TestClipViralSegments:
    def test_source_not_found_raises(self):
        clips = [ViralClip(start=0, end=30, title="Test", virality_score=5)]
        with pytest.raises(ClipperError, match="Source video not found"):
            clip_viral_segments(
                source_path="/nonexistent/path/video.mp4",
                viral_clips=clips,
            )

    @patch("pipeline.clipper.clip_video")
    def test_returns_paths_for_each_clip(self, mock_clip):
        """Should return one path per clip."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_text("fake video")

            mock_clip.side_effect = lambda **kwargs: kwargs["output_path"]

            clips = [
                ViralClip(start=0, end=30, title="A", virality_score=8),
                ViralClip(start=60, end=90, title="B", virality_score=7),
            ]

            paths = clip_viral_segments(
                source_path=str(source),
                viral_clips=clips,
                output_dir=Path(tmp) / "out",
                video_id="test",
            )
            assert len(paths) == 2

    @patch("pipeline.clipper.clip_video")
    def test_failed_clip_returns_empty_string(self, mock_clip):
        """Failed clips should return '' in the list."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_text("fake video")

            mock_clip.side_effect = ClipperError("FFmpeg failed")

            clips = [ViralClip(start=0, end=30, title="Fail", virality_score=5)]
            paths = clip_viral_segments(
                source_path=str(source),
                viral_clips=clips,
                output_dir=Path(tmp) / "out",
                video_id="test",
            )
            assert paths == [""]

    @patch("pipeline.clipper.clip_video")
    def test_output_filename_format(self, mock_clip):
        """Output files should be named {video_id}_clip_{index:02d}.mp4."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_text("fake video")

            def capture_clip(**kwargs):
                return kwargs["output_path"]

            mock_clip.side_effect = capture_clip

            clips = [ViralClip(start=0, end=30, title="A", virality_score=5)]
            paths = clip_viral_segments(
                source_path=str(source),
                viral_clips=clips,
                output_dir=Path(tmp) / "out",
                video_id="abc123",
            )
            assert "abc123_clip_00.mp4" in paths[0]
