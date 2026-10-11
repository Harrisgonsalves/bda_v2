from datetime import datetime, timezone
from app.core.config import settings
from app.recommender import artifacts, hybrid
from app.services import feature_service as fs


def refresh(db, student_id: int, module: str, presentation: str, version: str | None = None):
    """Re-rank candidates with existing artifacts + latest features. Returns list or None if no model yet."""
    version = version or artifacts.active_version(db)
    if not version:
        return None
    art = artifacts.load_artifact(version, module, presentation)
    if art is None:
        return None
    feats = fs.get_features(db, student_id, module, presentation)
    exclude = {int(k) for k, v in feats["weights"].items() if v > 0}
    exclude |= set(feats.get("completed", [])) | set(feats.get("disliked", []))
    recs = hybrid.recommend(art, feats["weights"], exclude, settings.alpha, settings.top_k_store)
    return store(db, student_id, module, presentation, version, recs)


def store(db, student_id, module, presentation, version, recs):
    q = {"student_id": student_id, "code_module": module, "code_presentation": presentation,
         "model_version": version}
    now = datetime.now(timezone.utc)
    titles = {r["id_site"]: r.get("title") for r in db.resources.find(
        {"code_module": module, "code_presentation": presentation,
         "id_site": {"$in": [r["resource_id"] for r in recs]}}, {"id_site": 1, "title": 1})}
    docs = [{**q, **r, "title": titles.get(r["resource_id"]), "created_at": now} for r in recs]
    db.recommendations.delete_many(q)
    if docs:
        db.recommendations.insert_many(docs, ordered=False)
    return [{k: v for k, v in d.items() if k != "_id"} for d in docs]


def get_or_refresh(db, student_id, module, presentation):
    version = artifacts.active_version(db)
    if not version:
        return None
    cur = list(db.recommendations.find(
        {"student_id": student_id, "code_module": module, "code_presentation": presentation,
         "model_version": version}, {"_id": 0}).sort("rank", 1))
    return cur or refresh(db, student_id, module, presentation, version)
