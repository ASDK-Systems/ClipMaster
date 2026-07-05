"""
YTAutomation — Pipeline Orchestrator

Chains all pipeline stages together into a single end-to-end flow.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings
from pipeline.clipper import clip_viral_segments
from pipeline.downloader import download_video
from pipeline.models import ClipResult, PipelineResult, ViralClip
from pipeline.subtitle_burner import burn_subtitles, generate_ass_subtitle
from pipeline.transcriber import transcribe_video
from pipeline.viral_detector import detect_viral_clips

logger = logging.getLogger(__name__)


def run_pipeline(
    url: str,
    num_clips: int = 5,
    crop_vertical: bool = True,
    subtitle_style: str = "tiktok",
    highlight_words: bool = True,
    on_progress: callable = None,
) -> PipelineResult:
    """
    Run the full viral clip extraction pipeline.

    Stages:
    1. Download video
    2. Transcribe (STT) the full video
    3. AI viral clip detection
    4. Clip/trim video at detected timestamps
    5. Transcribe each clip (for accurate per-clip subtitles)
    6. Generate & burn subtitles

    Args:
        url: YouTube video URL
        num_clips: Number of viral clips to extract
        crop_vertical: Crop clips to 9:16 for Shorts/Reels
        subtitle_style: Subtitle style preset name
        highlight_words: Use word-by-word highlight animation
        on_progress: Optional callback(stage: str, detail: str) for progress updates

    Returns:
        PipelineResult with all outputs
    """
    settings.ensure_dirs()

    def _progress(stage: str, detail: str = "") -> None:
        msg = f"[{stage}] {detail}" if detail else f"[{stage}]"
        logger.info(msg)
        if on_progress:
            on_progress(stage, detail)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 1: Download
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _progress("DOWNLOAD", f"Downloading video from {url}")
    metadata = download_video(url, on_progress=_progress)
    _progress("DOWNLOAD", f"Downloaded: {metadata.title} ({metadata.duration_seconds:.0f}s)")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 2: Full Video STT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _progress("TRANSCRIBE", "Transcribing full video...")
    full_transcript = transcribe_video(metadata.file_path, on_progress=_progress)
    _progress(
        "TRANSCRIBE",
        f"Done: {len(full_transcript.segments)} segments, {len(full_transcript.words)} words",
    )

    # Handle empty transcript (e.g., music-only video)
    if not full_transcript.segments:
        logger.warning("No speech detected in video — skipping viral detection")
        return PipelineResult(
            video_metadata=metadata,
            full_transcript=full_transcript,
            status="completed_no_speech",
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 3: AI Viral Detection
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _progress("ANALYZE", f"Detecting {num_clips} viral clips with AI...")
    viral_clips = detect_viral_clips(full_transcript, metadata, num_clips=num_clips)
    _progress("ANALYZE", f"Found {len(viral_clips)} viral candidates")

    if not viral_clips:
        logger.warning("No viral clips detected")
        return PipelineResult(
            video_metadata=metadata,
            full_transcript=full_transcript,
            status="completed_no_clips",
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 4: Clip & Trim
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _progress("CLIP", f"Extracting {len(viral_clips)} clips from video...")
    clip_paths = clip_viral_segments(
        source_path=metadata.file_path,
        viral_clips=viral_clips,
        crop_vertical=crop_vertical,
        video_id=metadata.video_id,
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 5 & 6: Per-clip STT + Subtitle Burning
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    clip_results: list[ClipResult] = []

    for i, (vc, clip_path) in enumerate(zip(viral_clips, clip_paths)):
        if not clip_path:
            logger.error("Clip %d failed, skipping subtitle step", i)
            clip_results.append(
                ClipResult(clip_index=i, viral_clip=vc, clip_file_path="")
            )
            continue

        _progress("SUBTITLE", f"Processing clip {i + 1}/{len(viral_clips)}: {vc.title}")

        # 5a: Transcribe the clip
        try:
            clip_transcript = transcribe_video(clip_path, on_progress=_progress)
        except Exception as e:
            logger.error("Clip %d transcription failed: %s", i, e)
            clip_results.append(
                ClipResult(
                    clip_index=i,
                    viral_clip=vc,
                    clip_file_path=clip_path,
                )
            )
            continue

        # 5b: Generate subtitle file
        output_dir = settings.output_dir
        sub_path = str(output_dir / f"{metadata.video_id}_clip_{i:02d}.ass")

        try:
            if clip_transcript.words:
                generate_ass_subtitle(
                    words=clip_transcript.words,
                    output_path=sub_path,
                    style_name=subtitle_style,
                    highlight_words=highlight_words,
                )
            else:
                logger.warning("No word-level timestamps for clip %d, skipping subtitles", i)
                clip_results.append(
                    ClipResult(
                        clip_index=i,
                        viral_clip=vc,
                        clip_file_path=clip_path,
                        transcript=clip_transcript,
                    )
                )
                continue
        except Exception as e:
            logger.error("Subtitle generation failed for clip %d: %s", i, e)
            clip_results.append(
                ClipResult(
                    clip_index=i,
                    viral_clip=vc,
                    clip_file_path=clip_path,
                    transcript=clip_transcript,
                )
            )
            continue

        # 5c: Burn subtitles into clip
        subtitled_path = str(output_dir / f"{metadata.video_id}_clip_{i:02d}_subtitled.mp4")

        try:
            burn_subtitles(
                video_path=clip_path,
                subtitle_path=sub_path,
                output_path=subtitled_path,
            )
        except Exception as e:
            logger.error("Subtitle burning failed for clip %d: %s", i, e)
            subtitled_path = ""

        clip_results.append(
            ClipResult(
                clip_index=i,
                viral_clip=vc,
                clip_file_path=clip_path,
                subtitle_file_path=sub_path,
                subtitled_file_path=subtitled_path,
                transcript=clip_transcript,
            )
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Done!
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    successful_clips = sum(1 for cr in clip_results if cr.subtitled_file_path)
    _progress("DONE", f"{successful_clips}/{len(viral_clips)} clips ready with subtitles")

    return PipelineResult(
        video_metadata=metadata,
        full_transcript=full_transcript,
        viral_clips_detected=viral_clips,
        clip_results=clip_results,
        status="completed",
    )
