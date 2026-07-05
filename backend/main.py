import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.api.routes import router as api_router
from config import settings

# Create FastAPI app
app = FastAPI(
    title="YTAutomation API",
    description="Backend API for viral clip extraction",
    version="0.1.0",
)

# CORS middleware for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api")

# Serve the output directory as static files so frontend can stream the clips
# Ensure the directory exists first
settings.ensure_dirs()
output_dir = str(settings.output_dir.absolute())

app.mount("/media", StaticFiles(directory=output_dir), name="media")

@app.get("/")
def read_root():
    return {"message": "YTAutomation API is running"}
