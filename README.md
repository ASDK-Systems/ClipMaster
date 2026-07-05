# 🎬 YTAutomation

AI-powered viral clip extraction from YouTube videos. Automatically download, transcribe, detect viral moments, clip, add trending subtitles, and publish — all from a single URL.

## Pipeline

```
YouTube URL → Download → STT (Whisper) → AI Viral Detection (GPT-4o)
→ Clip & Trim → STT on Clips → Burn Subtitles → Publish
```

## Quick Start

### Prerequisites

- **Python 3.11+**
- **FFmpeg** (with libass for styled subtitles): `brew install ffmpeg`
- **Docker** (for PostgreSQL + Redis): `brew install --cask docker`
- **OpenAI API key**: [platform.openai.com](https://platform.openai.com)

### Setup

```bash
# Clone and navigate
cd YTAutomation

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy env template and fill in your API keys
cp .env.example .env
# Edit .env with your OpenAI API key

# Start services (PostgreSQL + Redis)
docker compose up -d
```

### Usage (CLI)

```bash
# Check dependencies
python cli/main.py check

# View video info
python cli/main.py info "https://www.youtube.com/watch?v=VIDEO_ID"

# Process a video (full pipeline)
python cli/main.py process "https://www.youtube.com/watch?v=VIDEO_ID"

# Options
python cli/main.py process "URL" \
  --clips 3 \            # Number of clips to extract
  --vertical \            # Crop to 9:16 for Shorts/Reels
  --style tiktok \        # Subtitle style (default, bold_centered, tiktok)
  --no-highlight          # Disable word-by-word animation
```

### Run Tests

```bash
pytest tests/ -v
```

## Architecture

| Layer | Tech |
|-------|------|
| Video Download | yt-dlp |
| Speech-to-Text | OpenAI Whisper API |
| AI Analysis | GPT-4o |
| Video Processing | FFmpeg |
| Backend | FastAPI + Celery + Redis |
| Database | PostgreSQL |
| Frontend | Next.js (coming soon) |
| Payments | Whop |

## Project Structure

```
YTAutomation/
├── cli/                    # CLI interface
│   └── main.py
├── pipeline/               # Core processing modules
│   ├── models.py           # Pydantic data models
│   ├── downloader.py       # YouTube video download
│   ├── transcriber.py      # Whisper STT
│   ├── viral_detector.py   # AI viral clip detection
│   ├── clipper.py          # FFmpeg video clipping
│   ├── subtitle_burner.py  # Subtitle generation & burning
│   └── orchestrator.py     # Pipeline orchestration
├── backend/                # FastAPI backend (Phase 2)
├── frontend/               # Next.js frontend (Phase 3)
├── tests/                  # Unit tests
├── config.py               # App configuration
├── pyproject.toml          # Python project config
├── docker-compose.yml      # Dev services
└── .env.example            # Environment template
```

## License

Private — All rights reserved.
