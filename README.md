# AI Driven Simulation Engine

## Backend (local)

Run the API server:

```bash
uvicorn backend.main:app --reload
```

Optional env:
- `GEMINI_THINKING_LEVEL` (default: `minimal`, set to `high` for production)
