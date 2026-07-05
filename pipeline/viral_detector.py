"""
YTAutomation — AI Viral Clip Detection

Uses a local Ollama model to analyze transcripts and identify viral-worthy segments.
Falls back to OpenAI GPT-4o if configured.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from config import settings
from pipeline.models import Transcript, VideoMetadata, ViralClip

logger = logging.getLogger(__name__)


class ViralDetectionError(Exception):
    """Raised when viral clip detection fails."""


SYSTEM_PROMPT = """You are an expert short-form video editor and social media strategist.
Your job is to analyze video transcripts and identify the most engaging, shareable segments
that would perform well as YouTube Shorts, TikTok videos, or Instagram Reels.

You understand what makes content engaging across different genres:
- Podcasts/Interviews: Strong hooks (controversial takes, surprising facts, bold statements), actionable advice
- Narrative/Stories: Thought-provoking concepts, plot twists, fascinating explanations, or emotional peaks
- General: Self-contained segments that make sense without context, natural cliffhangers or punchlines

Rules:
1. Each clip should be 30-90 seconds long (ideal for Shorts/Reels)
2. Clips must be self-contained — a viewer with zero context should understand and enjoy it
3. Start timestamps should begin BEFORE the hook (give 1-2 seconds of lead-in)
4. End timestamps should be AFTER the payoff/punchline (don't cut mid-sentence)
5. You MUST return the requested number of clips, even if the content isn't a traditional podcast. Find the absolute most engaging moments available in the provided text."""

USER_PROMPT_TEMPLATE = """Analyze the following video transcript and identify {num_clips} viral clip candidates.

**Video Title:** {title}
**Channel:** {channel}
**Total Duration:** {duration}

**TRANSCRIPT:**
{transcript}

---

For each clip, respond with a JSON array. Each element must have:
- "start": start time in TOTAL SECONDS (float). For example, if the timestamp is [01:20], write 80.0 (NOT 1.20).
- "end": end time in TOTAL SECONDS (float). For example, if the timestamp is [02:05], write 125.0.
- "title": catchy title optimized for YouTube Shorts (max 60 chars)
- "hook_description": what makes the first 3 seconds grab attention
- "virality_score": 1-10 rating of viral potential
- "reasoning": 1-2 sentence explanation of why this clip will perform well

Respond with ONLY the JSON array, no other text. Example:
[
  {{
    "start": 125.5,
    "end": 187.2,
    "title": "This Changed Everything I Knew About...",
    "hook_description": "Speaker drops a controversial statement that challenges conventional wisdom",
    "virality_score": 8.5,
    "reasoning": "Strong pattern interrupt opening, delivers a complete surprising insight, ends on a quotable line."
  }}
]"""


def _format_transcript_for_prompt(transcript: Transcript, max_chars: int = 80000) -> str:
    """
    Format transcript segments with timestamps for the AI prompt.

    Truncates if needed to fit context window.
    """
    lines = []
    for seg in transcript.segments:
        timestamp = _seconds_to_timestamp(seg.start)
        lines.append(f"[{timestamp}] {seg.text}")

    full_text = "\n".join(lines)

    # Truncate if too long (with overlap note)
    if len(full_text) > max_chars:
        logger.warning(
            "Transcript is %d chars, truncating to %d for AI prompt",
            len(full_text),
            max_chars,
        )
        full_text = full_text[:max_chars] + "\n\n[... transcript truncated due to length ...]"

    return full_text


def _seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS format."""
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _strip_markdown(text: str) -> str:
    """Strip markdown code block wrappers if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json or ``` prefix
        try:
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
        except ValueError:
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _parse_ai_response(response_text: str) -> list[dict]:
    """
    Parse the AI response into a list.
    """
    text = _strip_markdown(response_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ViralDetectionError(
            f"AI returned invalid JSON. Response was:\n{response_text[:500]}\n\nError: {e}"
        ) from e

    if not isinstance(data, list):
        raise ViralDetectionError(
            f"AI response is not a JSON array. Got: {type(data).__name__}"
        )

    return data


def _validate_clips(
    raw_clips: list[dict],
    video_duration: float,
) -> list[ViralClip]:
    """
    Validate and sanitize AI-generated clip data.

    - Clamps timestamps to valid range
    - Filters out clips that are too short or too long
    - Sorts by virality score (descending)
    """
    valid_clips = []

    for i, clip_data in enumerate(raw_clips):
        try:
            start = float(clip_data.get("start", 0))
            end = float(clip_data.get("end", 0))

            # Clamp to video bounds
            start = max(0, min(start, video_duration))
            end = max(0, min(end, video_duration))

            # Ensure start < end
            if start >= end:
                logger.warning("Clip %d has invalid timestamps (start=%s, end=%s), skipping", i, start, end)
                continue

            duration = end - start

            # Filter: too short (<10s) or too long (>120s)
            if duration < 10:
                logger.warning("Clip %d is too short (%.1fs), skipping", i, duration)
                continue
            if duration > 120:
                logger.warning("Clip %d is too long (%.1fs), trimming to 90s", i, duration)
                end = start + 90

            clip = ViralClip(
                start=start,
                end=end,
                title=clip_data.get("title", f"Clip {i + 1}"),
                hook_description=clip_data.get("hook_description", ""),
                virality_score=min(10, max(0, float(clip_data.get("virality_score", 5)))),
                reasoning=clip_data.get("reasoning", ""),
            )
            valid_clips.append(clip)

        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse clip %d: %s", i, e)
            continue

    # Sort by virality score (best first)
    valid_clips.sort(key=lambda c: c.virality_score, reverse=True)

    return valid_clips


def detect_viral_clips(
    transcript: Transcript,
    metadata: VideoMetadata,
    num_clips: int = 5,
) -> list[ViralClip]:
    """
    Analyze a transcript and identify viral clip candidates using AI.

    Args:
        transcript: Full video transcript with timestamps
        metadata: Video metadata (title, channel, duration)
        num_clips: Number of clips to request from AI

    Returns:
        List of ViralClip objects, sorted by virality_score descending
    """
    if not transcript.segments:
        logger.warning("Empty transcript — cannot detect viral clips")
        return []

    num_clips = min(num_clips, settings.max_clips_per_video)

    # Format transcript for prompt
    formatted_transcript = _format_transcript_for_prompt(transcript)

    # Format duration
    duration_str = _seconds_to_timestamp(metadata.duration_seconds)

    # Build the prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        num_clips=num_clips,
        title=metadata.title,
        channel=metadata.channel,
        duration=duration_str,
        transcript=formatted_transcript,
    )

    logger.info(
        "Requesting %d viral clips from Ollama (%s) at %s (prompt: %d chars)",
        num_clips,
        settings.ollama_model,
        settings.ollama_base_url,
        len(user_prompt),
    )

    # Call Ollama via its OpenAI-compatible API
    client = OpenAI(
        base_url=settings.ollama_base_url,
        api_key="ollama",  # Ollama doesn't need a real key but the client requires one
    )

    try:
        response = client.chat.completions.create(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
    except Exception as e:
        raise ViralDetectionError(f"AI API call failed: {e}") from e

    response_text = response.choices[0].message.content
    if not response_text:
        logger.warning("AI returned an empty response. Model may have hit context limits or errored internally. Returning 0 clips.")
        return []

    logger.info("AI response received (%d chars)", len(response_text))

    # Parse response — Ollama models may return markdown-wrapped JSON,
    # a raw array, or a {"clips": [...]} object. Handle all cases.
    try:
        # First try _parse_ai_response which handles markdown code blocks and expects a list
        raw_clips = _parse_ai_response(response_text)
    except ViralDetectionError:
        # If that fails (e.g. it's a dict), strip markdown and try parsing as a JSON object
        clean_text = _strip_markdown(response_text)
        try:
            parsed = json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.warning(f"AI returned unparseable JSON. Attempting regex salvage. Error: {e}")
            raw_clips = _salvage_clips(clean_text)
            parsed = {} # Bypass dict check if salvaged
            
        if not raw_clips and isinstance(parsed, dict):
            for key in ("clips", "viral_clips", "results", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    raw_clips = parsed[key]
                    break
            else:
                raise ViralDetectionError(
                    f"AI returned a JSON object without a recognized clips array. "
                    f"Keys: {list(parsed.keys())}"
                )
        elif isinstance(parsed, list):
            raw_clips = parsed
        else:
            raise ViralDetectionError(
                f"Unexpected AI response type: {type(parsed).__name__}"
            )

    # Validate and sanitize
    clips = _validate_clips(raw_clips, metadata.duration_seconds)

    logger.info("Validated %d viral clips (from %d AI candidates)", len(clips), len(raw_clips))

    return clips
