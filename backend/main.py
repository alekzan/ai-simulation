from pathlib import Path
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.db import init_db
from backend.routes.metrics import router as metrics_router
from backend.routes.title import router as title_router
from backend.routes.init import router as init_router
from backend.routes.turn import router as turn_router
from backend.ephemeral_media import get_media, prune_expired_media

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
MEDIA_DIR = ROOT_DIR / "media"


def load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


load_env()

app = FastAPI(title="AI Driven Simulation Engine")


@app.on_event("startup")
def startup() -> None:
    init_db()

app.include_router(title_router)
app.include_router(init_router)
app.include_router(turn_router)
app.include_router(metrics_router)

FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/ephemeral/{token}")
def serve_ephemeral(token: str, request: Request) -> Response:
    prune_expired_media()
    resolved = get_media(token)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Media expired or missing.")
    data, mime_type = resolved
    total_size = len(data)
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=300",
    }

    range_header = request.headers.get("range")

    # Use full response when no range requested.
    if not range_header:
        headers["Content-Length"] = str(total_size)
        return Response(content=data, media_type=mime_type, headers=headers)

    match = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not match:
        headers["Content-Range"] = f"bytes */{total_size}"
        return Response(status_code=416, headers=headers)

    start_s, end_s = match.groups()
    if start_s == "" and end_s == "":
        headers["Content-Length"] = str(total_size)
        return Response(content=data, media_type=mime_type, headers=headers)

    if start_s == "":
        suffix = int(end_s)
        start = max(total_size - suffix, 0)
        end = total_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else total_size - 1

    if start >= total_size or start > end:
        headers["Content-Range"] = f"bytes */{total_size}"
        return Response(status_code=416, headers=headers)

    end = min(end, total_size - 1)
    chunk = data[start : end + 1]
    headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
    headers["Content-Length"] = str(len(chunk))
    return Response(content=chunk, status_code=206, media_type=mime_type, headers=headers)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
