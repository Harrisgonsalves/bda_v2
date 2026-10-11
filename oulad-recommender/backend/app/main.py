from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api import admin, auth, student
from app.db.indexes import create_indexes


@asynccontextmanager
async def lifespan(app):
    create_indexes()
    yield


app = FastAPI(title="COURSE Recommender API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, student.router, admin.router):
    app.include_router(r, prefix="/api/v1")


# Demo-level: generated graph files (student IDs only) are served without auth
app.mount("/api/v1/static", StaticFiles(directory=str(settings.static_dir)), name="static")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
