from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import init_db

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock_mode": settings.mock_mode}


app.include_router(router)
