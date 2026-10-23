from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import BASE_DIR, settings
from app.db.init_db import init_db

DIST_DIR = BASE_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cardridz — учёт картриджей",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


if DIST_DIR.exists():
    app.mount(
        "/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(DIST_DIR / "index.html")
else:

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": "Cardridz API",
            "docs": "/docs",
            "hint": "Соберите фронтенд: cd frontend && npm install && npm run build",
        }
