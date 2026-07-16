"""
YTAutomation — Video Downloader

Downloads YouTube videos using yt-dlp with metadata extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yt_dlp

from config import settings
from pipeline.models import VideoMetadata

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when video download fails."""


def _validate_url(url: str) -> str:
    """Basic validation that this looks like a YouTube URL."""
    url = url.strip()
    valid_prefixes = (
        "https://www.youtube.com/",
        "https://youtube.com/",
        "https://youtu.be/",
        "http://www.youtube.com/",
        "http://youtube.com/",
        "http://youtu.be/",
    )
    if not any(url.startswith(p) for p in valid_prefixes):
        raise DownloadError(
            f"Invalid YouTube URL: {url}. "
            "Must start with https://www.youtube.com/, https://youtu.be/, etc."
        )
    return url


def download_video(
    url: str,
    output_dir: Path | None = None,
    max_duration_minutes: int | None = None,
    on_progress: callable = None,
) -> VideoMetadata:
    """
    Download a YouTube video and return its metadata.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the video (default: settings.downloads_dir)
        max_duration_minutes: Max video duration to allow (default: settings value)
        on_progress: Optional callback for progress logs

    Returns:
        VideoMetadata with file_path populated

    Raises:
        DownloadError: If download fails or video exceeds duration limit
    """
    url = _validate_url(url)
    output_dir = output_dir or settings.downloads_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    max_duration = max_duration_minutes or settings.max_video_duration_minutes

    # Step 1: Extract metadata first (without downloading)
    logger.info("Extracting metadata for: %s", url)
    meta_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
    if settings.youtube_cookies_from_browser:
        meta_opts["cookiesfrombrowser"] = (settings.youtube_cookies_from_browser,)

    try:
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(f"Failed to extract video info: {e}") from e

    if info is None:
        raise DownloadError("No video info returned — URL may be invalid or private.")

    # Check if it's a live stream
    if info.get("is_live"):
        raise DownloadError("Live streams are not supported. Please use a recorded video.")

    # Check duration
    duration = info.get("duration", 0)
    if duration > max_duration * 60:
        raise DownloadError(
            f"Video is {duration / 60:.0f} minutes long, "
            f"which exceeds the {max_duration}-minute limit."
        )

    video_id = info.get("id", "unknown")
    title = info.get("title", "Untitled")

    # Build metadata
    metadata = VideoMetadata(
        url=url,
        video_id=video_id,
        title=title,
        channel=info.get("uploader", info.get("channel", "Unknown")),
        duration_seconds=duration,
        thumbnail_url=info.get("thumbnail", ""),
        description=info.get("description", ""),
        upload_date=info.get("upload_date", ""),
    )

    # Step 2: Download the video
    logger.info("Downloading video: %s (%s)", title, _format_duration(duration))
    
    def internal_progress_hook(d: dict) -> None:
        """Log download progress and send to GUI."""
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "?%")
            speed = d.get("_speed_str", "?")
            eta = d.get("_eta_str", "?")
            msg = f"↓ {pct} at {speed} — ETA: {eta}"
            if on_progress:
                on_progress("DOWNLOAD", msg)
            # Prevent excessive terminal spam for fast downloads
            # logger.info(msg) 
        elif d["status"] == "finished":
            if on_progress:
                on_progress("DOWNLOAD", "✓ Download finished, extracting video...")
            logger.info("  ✓ Download finished, merging formats...")

    output_template = str(output_dir / f"{video_id}.%(ext)s")

    download_opts: dict = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "progress_hooks": [internal_progress_hook],
        # Retry configuration
        "retries": 3,
        "fragment_retries": 3,
    }

    if settings.ffmpeg_location:
        download_opts["ffmpeg_location"] = settings.ffmpeg_location

    if settings.youtube_cookies_from_browser:
        download_opts["cookiesfrombrowser"] = (settings.youtube_cookies_from_browser,)

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(f"Download failed: {e}") from e

    # Find the downloaded file
    video_file = output_dir / f"{video_id}.mp4"
    if not video_file.exists():
        # yt-dlp may have used a different extension, search for it
        candidates = list(output_dir.glob(f"{video_id}.*"))
        video_files = [f for f in candidates if f.suffix in (".mp4", ".mkv", ".webm")]
        if not video_files:
            raise DownloadError(
                f"Download appeared to succeed but no video file found at {video_file}"
            )
        video_file = video_files[0]

    metadata.file_path = str(video_file)
    logger.info("Download complete: %s (%.1f MB)", video_file, video_file.stat().st_size / 1e6)

    return metadata





def _format_duration(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
