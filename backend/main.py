from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.db import init_db
from backend.routes.title import router as title_router


def load_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    load_dotenv(root_dir / ".env")


load_env()

app = FastAPI(title="AI Driven Simulation Engine")


@app.on_event("startup")
def startup() -> None:
    init_db()

app.include_router(title_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
