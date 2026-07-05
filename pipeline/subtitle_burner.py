"""
YTAutomation — Subtitle Generation & Burning

Generates styled ASS subtitles and burns them into video clips using FFmpeg.
Supports the trendy word-by-word highlight animation style.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from config import settings
from pipeline.models import Transcript, TranscriptWord

logger = logging.getLogger(__name__)


class SubtitleError(Exception):
    """Raised when subtitle generation or burning fails."""


# --- ASS Subtitle Style Presets ---

STYLE_PRESETS = {
    "default": {
        "font": "Arial",
        "fontsize": 20,
        "primary_color": "&H00FFFFFF",    # White
        "outline_color": "&H00000000",    # Black
        "back_color": "&H80000000",       # Semi-transparent black
        "bold": True,
        "outline": 2,
        "shadow": 1,
        "alignment": 2,                    # Bottom center
        "margin_v": 40,
    },
    "bold_centered": {
        "font": "Impact",
        "fontsize": 24,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": True,
        "outline": 3,
        "shadow": 0,
        "alignment": 5,                    # Middle center
        "margin_v": 20,
    },
    "tiktok": {
        "font": "Montserrat",
        "fontsize": 22,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": True,
        "outline": 3,
        "shadow": 0,
        "alignment": 2,                    # Bottom center
        "margin_v": 60,
    },
}

# Highlight color for the word-by-word animation (yellow)
HIGHLIGHT_COLOR = "&H0000FFFF"  # Yellow in ASS (AABBGGRR)


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format: H:MM:SS.CC"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int((s % 1) * 100)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    """Escape special characters for ASS subtitle format."""
    # ASS uses { } for override tags, so we need to escape literal braces
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text


def generate_ass_subtitle(
    words: list[TranscriptWord],
    output_path: str,
    style_name: str = "tiktok",
    highlight_words: bool = True,
    words_per_group: int = 3,
) -> str:
    """
    Generate an ASS subtitle file with word-by-word highlight animation.

    The "karaoke" effect highlights each word as it's spoken, which is the
    trending caption style on TikTok, Reels, and Shorts.

    Args:
        words: Word-level transcript with timestamps
        output_path: Where to save the .ass file
        style_name: Style preset name
        highlight_words: If True, use word-by-word highlight animation
        words_per_group: Number of words to show at once

    Returns:
        Path to the generated .ass file
    """
    if not words:
        raise SubtitleError("No words provided for subtitle generation")

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["tiktok"])

    # ASS header
    header = f"""[Script Info]
Title: YTAutomation Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{style['fontsize']},{style['primary_color']},&H000000FF,{style['outline_color']},{style['back_color']},{'-1' if style['bold'] else '0'},0,0,0,100,100,0,0,1,{style['outline']},{style['shadow']},{style['alignment']},20,20,{style['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Generate dialogue lines
    dialogue_lines = []

    if highlight_words and len(words) > 1:
        # Word-by-word highlight mode
        # Group words into chunks
        groups = []
        for i in range(0, len(words), words_per_group):
            group = words[i : i + words_per_group]
            groups.append(group)

        for group in groups:
            group_start = group[0].start
            group_end = group[-1].end

            start_ts = _seconds_to_ass_time(group_start)
            end_ts = _seconds_to_ass_time(group_end)

            # Build the text with karaoke-style override tags
            # Each word gets highlighted in sequence
            text_parts = []
            for j, word in enumerate(group):
                word_text = _escape_ass_text(word.word.strip())

                if not word_text:
                    continue

                # Calculate duration of this word in centiseconds
                word_duration_cs = int((word.end - word.start) * 100)

                # Use \kf (smooth fill) for highlight animation
                text_parts.append(f"{{\\kf{word_duration_cs}}}{word_text}")

            text = " ".join(text_parts) if not text_parts else "".join(text_parts)

            # Add the dialogue line
            line = f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}"
            dialogue_lines.append(line)

    else:
        # Simple mode: show groups of words without highlight
        for i in range(0, len(words), words_per_group):
            group = words[i : i + words_per_group]
            group_start = group[0].start
            group_end = group[-1].end

            start_ts = _seconds_to_ass_time(group_start)
            end_ts = _seconds_to_ass_time(group_end)

            text = " ".join(_escape_ass_text(w.word.strip()) for w in group if w.word.strip())
            line = f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}"
            dialogue_lines.append(line)

    # Write the file
    content = header + "\n".join(dialogue_lines) + "\n"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Generated ASS subtitle: %s (%d lines)", output_path, len(dialogue_lines))
    return output_path


def generate_srt_subtitle(
    words: list[TranscriptWord],
    output_path: str,
    words_per_group: int = 6,
) -> str:
    """
    Generate a standard SRT subtitle file (fallback if ASS doesn't work).

    Args:
        words: Word-level transcript
        output_path: Where to save the .srt file
        words_per_group: Words per subtitle line

    Returns:
        Path to the generated .srt file
    """
    if not words:
        raise SubtitleError("No words provided for subtitle generation")

    lines = []
    counter = 1

    for i in range(0, len(words), words_per_group):
        group = words[i : i + words_per_group]
        start = group[0].start
        end = group[-1].end
        text = " ".join(w.word.strip() for w in group if w.word.strip())

        if not text:
            continue

        start_ts = _seconds_to_srt_time(start)
        end_ts = _seconds_to_srt_time(end)

        lines.append(f"{counter}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")
        counter += 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Generated SRT subtitle: %s (%d entries)", output_path, counter - 1)
    return output_path


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
) -> str:
    """
    Burn (hardcode) subtitles into a video using FFmpeg.

    Args:
        video_path: Input video file
        subtitle_path: Path to .ass or .srt subtitle file
        output_path: Output video with burned subtitles

    Returns:
        Path to the output video

    Raises:
        SubtitleError: If burning fails
    """
    logger.info("Burning subtitles into: %s", video_path)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Determine the subtitle filter based on file extension
    sub_ext = Path(subtitle_path).suffix.lower()
    
    # FFmpeg filter graph syntax requires escaping colons and backslashes
    escaped_path = str(subtitle_path).replace('\\', '\\\\').replace(':', '\\:')

    if sub_ext == ".ass":
        # Use the 'ass' filter for ASS files (preserves all styling)
        vf_filter = f"ass={escaped_path}"
    else:
        # Use the 'subtitles' filter for SRT/VTT (uses libass internally)
        vf_filter = f"subtitles={escaped_path}"

    cmd = [
        settings.ffmpeg_location or "ffmpeg",
        "-i", video_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "copy",                # Copy audio (no re-encode needed)
        "-movflags", "+faststart",
        "-y",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Check if it's a libass issue
        if "libass" in result.stderr.lower() or "No such filter" in result.stderr:
            logger.warning(
                "ASS filter failed (libass may not be installed). "
                "Falling back to drawtext approach..."
            )
            return _burn_subtitles_drawtext(video_path, subtitle_path, output_path)

        raise SubtitleError(f"FFmpeg subtitle burn failed: {result.stderr}")

    if not Path(output_path).exists():
        raise SubtitleError(f"Output video was not created: {output_path}")

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info("Subtitled video created: %s (%.1f MB)", output_path, file_size_mb)

    return output_path


def _burn_subtitles_drawtext(
    video_path: str,
    subtitle_path: str,
    output_path: str,
) -> str:
    """
    Fallback: burn subtitles using FFmpeg's 'subtitles' filter with SRT.

    Used when libass is not available for ASS rendering.
    """
    # If the subtitle is ASS, we need to convert to SRT first
    if Path(subtitle_path).suffix.lower() == ".ass":
        logger.warning("ASS subtitles not supported without libass; subtitle styles will be basic")

    escaped_path = str(subtitle_path).replace('\\', '\\\\').replace(':', '\\:')

    cmd = [
        settings.ffmpeg_location or "ffmpeg",
        "-i", video_path,
        "-vf", f"subtitles={escaped_path}:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Bold=1'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-y",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SubtitleError(f"Drawtext subtitle burn also failed: {result.stderr}")

    return output_path
