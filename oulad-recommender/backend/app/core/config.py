import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


class Settings:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "oulad_recommender")
    jwt_secret = os.getenv("JWT_SECRET", "dev-only-secret-change-me")
    jwt_alg = "HS256"
    jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    models_dir = Path(os.getenv("MODELS_DIR", str(ROOT / "models"))).resolve()
    alpha = float(os.getenv("HYBRID_ALPHA", "0.5"))
    rscript = os.getenv("RSCRIPT_PATH", "Rscript")
    static_dir = ROOT / "backend" / "static"
    top_k_store = 20          # recommendations stored per student/course
    max_batch_events = 500
    max_range_days = 365


settings = Settings()
settings.models_dir.mkdir(parents=True, exist_ok=True)
(settings.static_dir / "network").mkdir(parents=True, exist_ok=True)
