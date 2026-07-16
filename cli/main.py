"""
YTAutomation — CLI Interface

Command-line interface for testing the pipeline end-to-end.
"""

from __future__ import annotations

import json
import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from config import settings

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure rich logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """YTAutomation — AI-powered viral clip extraction from YouTube videos."""
    setup_logging(verbose)


@cli.command()
@click.argument("url")
@click.option("--clips", "-n", default=5, help="Number of clips to extract")
@click.option("--vertical/--no-vertical", default=True, help="Crop to 9:16 vertical")
@click.option("--style", default="tiktok", help="Subtitle style preset")
@click.option("--no-highlight", is_flag=True, help="Disable word-by-word highlight")
def process(url: str, clips: int, vertical: bool, style: str, no_highlight: bool) -> None:
    """Process a YouTube video URL and extract viral clips."""
    from pipeline.orchestrator import run_pipeline

    console.print(
        Panel(
            f"[bold]🎬 Processing:[/bold] {url}\n"
            f"[dim]Clips: {clips} | Vertical: {vertical} | Style: {style}[/dim]",
            title="YTAutomation",
            border_style="blue",
        )
    )

    def on_progress(stage: str, detail: str) -> None:
        emoji_map = {
            "DOWNLOAD": "⬇️",
            "TRANSCRIBE": "🗣️",
            "ANALYZE": "🤖",
            "CLIP": "✂️",
            "SUBTITLE": "🔤",
            "DONE": "✅",
        }
        emoji = emoji_map.get(stage, "▶️")
        console.print(f"  {emoji} [bold]{stage}[/bold] {detail}")

    try:
        result = run_pipeline(
            url=url,
            num_clips=clips,
            crop_vertical=vertical,
            subtitle_style=style,
            highlight_words=not no_highlight,
            on_progress=on_progress,
        )
    except Exception as e:
        console.print(f"\n[red bold]❌ Pipeline failed:[/red bold] {e}")
        sys.exit(1)

    # Display results
    console.print()

    if not result.clip_results:
        console.print("[yellow]⚠️  No clips were generated.[/yellow]")
        return

    table = Table(title="🎬 Generated Clips", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", min_width=30)
    table.add_column("Duration", justify="right")
    table.add_column("Score", justify="center")
    table.add_column("File", style="dim")

    for cr in result.clip_results:
        duration = f"{cr.viral_clip.duration:.0f}s"
        score = f"{'⭐' * int(cr.viral_clip.virality_score / 2)}"
        file_path = cr.subtitled_file_path or cr.clip_file_path or "❌ Failed"

        table.add_row(
            str(cr.clip_index + 1),
            cr.viral_clip.title,
            duration,
            f"{cr.viral_clip.virality_score:.1f} {score}",
            file_path,
        )

    console.print(table)
    console.print()

    successful = sum(1 for cr in result.clip_results if cr.subtitled_file_path)
    console.print(
        f"[green bold]✅ {successful}/{len(result.clip_results)} clips ready![/green bold]"
    )
    console.print(f"[dim]Output directory: {settings.output_dir}[/dim]")


@cli.command()
@click.argument("url")
def info(url: str) -> None:
    """Show metadata for a YouTube video without downloading."""
    from pipeline.downloader import download_video, _validate_url

    import yt_dlp

    console.print(f"[dim]Fetching info for: {url}[/dim]")

    _validate_url(url)

    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        console.print("[red]Could not fetch video info[/red]")
        return

    duration = info.get("duration", 0)
    h, r = divmod(duration, 3600)
    m, s = divmod(r, 60)
    dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    console.print(
        Panel(
            f"[bold]{info.get('title', 'Unknown')}[/bold]\n"
            f"Channel: {info.get('uploader', 'Unknown')}\n"
            f"Duration: {dur_str}\n"
            f"Views: {info.get('view_count', 'N/A'):,}\n"
            f"Upload Date: {info.get('upload_date', 'N/A')}\n"
            f"Description: {(info.get('description', '') or '')[:200]}...",
            title="Video Info",
            border_style="green",
        )
    )


@cli.command()
def check() -> None:
    """Check that all required dependencies are installed."""
    import subprocess

    checks = {
        "FFmpeg": ["ffmpeg", "-version"],
        "FFprobe": ["ffprobe", "-version"],
        "Python": [sys.executable, "--version"],
    }

    console.print("[bold]🔍 Dependency Check[/bold]\n")

    all_good = True
    for name, cmd in checks.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            version = result.stdout.split("\n")[0] if result.stdout else "OK"
            console.print(f"  ✅ {name}: {version}")
        except FileNotFoundError:
            console.print(f"  ❌ {name}: NOT FOUND")
            all_good = False

    # Check API keys & services
    console.print()
    if settings.openai_api_key:
        masked = settings.openai_api_key[:8] + "..." + settings.openai_api_key[-4:]
        console.print(f"  🔑 OpenAI API Key (Whisper STT): {masked}")
    else:
        console.print("  ❌ OpenAI API Key: NOT SET (needed for Whisper STT)")
        all_good = False

    # Check Gemini or Ollama, depending on config
    console.print()
    import httpx

    use_gemini = settings.use_gemini and bool(settings.gemini_api_key)

    if use_gemini:
        try:
            resp = httpx.get(
                settings.gemini_base_url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {settings.gemini_api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                console.print(f"  ✅ Gemini: reachable at {settings.gemini_base_url}")
                console.print(f"  ✅ Gemini model configured: {settings.gemini_model}")
            elif resp.status_code == 401 or resp.status_code == 403:
                console.print(f"  ❌ Gemini: API key rejected (status {resp.status_code})")
                all_good = False
            else:
                console.print(f"  ❌ Gemini: responded with status {resp.status_code}")
                all_good = False
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            console.print(f"  ❌ Gemini: not reachable ({e})")
            all_good = False
    else:
        try:
            resp = httpx.get(
                settings.ollama_base_url.replace("/v1", "/api/tags"),
                timeout=5,
            )
            if resp.status_code == 200:
                models_data = resp.json()
                model_names = [m["name"] for m in models_data.get("models", [])]
                console.print(
                    f"  ✅ Ollama: running at {settings.ollama_base_url} "
                    f"({len(model_names)} models)"
                )

                # Check if the configured model is pulled
                configured = settings.ollama_model
                # Match with or without :latest tag
                matched = any(
                    m == configured or m == f"{configured}:latest" or configured == m.split(":")[0]
                    for m in model_names
                )
                if matched:
                    console.print(f"  ✅ Ollama model: {configured}")
                else:
                    console.print(
                        f"  ⚠️  Ollama model '{configured}' not found. "
                        f"Available: {', '.join(model_names[:5])}"
                    )
                    console.print(f"     Run: [bold]ollama pull {configured}[/bold]")
                    all_good = False
            else:
                console.print(f"  ❌ Ollama: responded with status {resp.status_code}")
                all_good = False
        except (httpx.ConnectError, httpx.TimeoutException):
            console.print(
                f"  ❌ Ollama: not reachable at {settings.ollama_base_url}\n"
                f"     Run: [bold]ollama serve[/bold]"
            )
            all_good = False

    if all_good:
        console.print("\n[green bold]✅ All checks passed![/green bold]")
    else:
        console.print("\n[red bold]❌ Some checks failed. See above.[/red bold]")


if __name__ == "__main__":
    cli()
