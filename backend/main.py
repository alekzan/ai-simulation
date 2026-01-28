from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI


def load_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    load_dotenv(root_dir / ".env")


load_env()

app = FastAPI(title="AI Driven Simulation Engine")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
