"""
YTAutomation — Video Clipper & Trimmer

Extracts clips from a source video at specified timestamps using FFmpeg.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from config import settings
from pipeline.models import ViralClip

logger = logging.getLogger(__name__)


class ClipperError(Exception):
    """Raised when video clipping fails."""


def _get_ffmpeg_cmd() -> str:
    """Get the ffmpeg command path."""
    return settings.ffmpeg_location or "ffmpeg"


def _get_ffprobe_cmd() -> str:
    """Get the ffprobe command path."""
    if settings.ffmpeg_location:
        ffmpeg_dir = Path(settings.ffmpeg_location).parent
        return str(ffmpeg_dir / "ffprobe")
    return "ffprobe"


def get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds."""
    cmd = [
        _get_ffprobe_cmd(),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ClipperError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def clip_video(
    source_path: str,
    start: float,
    end: float,
    output_path: str,
    crop_vertical: bool = False,
) -> str:
    """
    Extract a clip from a source video.

    Uses a two-pass approach:
    1. Fast seek to near the start point (-ss before -i)
    2. Precise trim with re-encoding for frame accuracy

    Args:
        source_path: Path to source video file
        start: Start time in seconds
        end: End time in seconds
        output_path: Path for the output clip
        crop_vertical: If True, auto-crop to 9:16 aspect ratio (center crop)

    Returns:
        Path to the output clip file
    """
    duration = end - start
    if duration <= 0:
        raise ClipperError(f"Invalid clip duration: {duration}s (start={start}, end={end})")

    logger.info(
        "Clipping: %.1fs → %.1fs (%.1fs) → %s",
        start, end, duration, output_path,
    )

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Build the FFmpeg command
    cmd = [
        _get_ffmpeg_cmd(),
        "-ss", str(start),          # Fast seek (before -i)
        "-i", source_path,
        "-t", str(duration),        # Duration of clip
        "-c:v", "libx264",          # Re-encode video (H.264)
        "-preset", "fast",          # Encoding speed
        "-crf", "23",               # Quality (lower = better, 18-28 typical)
        "-c:a", "aac",              # Re-encode audio
        "-b:a", "128k",             # Audio bitrate
        "-movflags", "+faststart",  # Web-optimized MP4
        "-avoid_negative_ts", "make_zero",
        "-y",                       # Overwrite output
    ]

    # Optional: crop to 9:16 vertical format
    if crop_vertical:
        # Center crop: take the middle portion of the frame
        # For a 1920x1080 source, this creates a 608x1080 crop → scaled to 1080x1920
        vf_filter = (
            "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"  # Crop to 9:16 from center
            "scale=1080:1920:flags=lanczos"         # Scale to 1080x1920
        )
        cmd.extend(["-vf", vf_filter])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ClipperError(f"FFmpeg clipping failed: {result.stderr}")

    if not Path(output_path).exists():
        raise ClipperError(f"Clip was not created at: {output_path}")

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info("Clip created: %s (%.1f MB)", output_path, file_size_mb)

    return output_path


def clip_viral_segments(
    source_path: str,
    viral_clips: list[ViralClip],
    output_dir: Path | None = None,
    crop_vertical: bool = False,
    video_id: str = "video",
) -> list[str]:
    """
    Extract multiple clips from a source video.

    Args:
        source_path: Path to source video
        viral_clips: List of ViralClip objects with start/end timestamps
        output_dir: Directory for output clips (default: settings.output_dir)
        crop_vertical: If True, crop clips to 9:16 vertical format
        video_id: ID for naming output files

    Returns:
        List of output file paths (in same order as viral_clips)
    """
    output_dir = output_dir or settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate source exists
    if not Path(source_path).exists():
        raise ClipperError(f"Source video not found: {source_path}")

    clip_paths = []

    for i, vc in enumerate(viral_clips):
        output_filename = f"{video_id}_clip_{i:02d}.mp4"
        output_path = str(output_dir / output_filename)

        try:
            path = clip_video(
                source_path=source_path,
                start=vc.start,
                end=vc.end,
                output_path=output_path,
                crop_vertical=crop_vertical,
            )
            clip_paths.append(path)
        except ClipperError as e:
            logger.error("Failed to clip segment %d (%s): %s", i, vc.title, e)
            clip_paths.append("")  # Empty string signals failure

    successful = sum(1 for p in clip_paths if p)
    logger.info("Clipped %d/%d segments successfully", successful, len(viral_clips))

    return clip_paths
