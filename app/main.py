"""Routes and startup."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

# Resolved from this file, not the working directory, so the app runs from anywhere.
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI Screenshot Repository")


@app.get("/")
def library_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
