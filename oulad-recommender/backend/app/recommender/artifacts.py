"""Build, save, load and cache per-course-presentation model artifacts."""
import time
from dataclasses import dataclass
from typing import Optional
import joblib
import numpy as np
import pandas as pd
from app.core.config import settings
from app.recommender.content_based import content_similarity
from app.recommender.collaborative import interaction_matrix, item_similarity, popularity


@dataclass
class Artifact:
    version: str
    code_module: str
    code_presentation: str
    item_ids: list          # id_site per column
    item_index: dict        # id_site -> column
    item_type: list
    item_week: list
    content_sim: np.ndarray
    cf_sim: np.ndarray
    popularity: np.ndarray
    n_students: int


def build_artifact(version, module, presentation, resources: pd.DataFrame, interactions: pd.DataFrame) -> Artifact:
    """resources: id_site, activity_type, week_from, code_module. interactions: student, item, weight."""
    resources = resources.sort_values("id_site").reset_index(drop=True)
    resources["week_from"] = pd.to_numeric(resources["week_from"], errors="coerce")  # "?" -> NaN
    item_ids = resources["id_site"].astype(int).tolist()
    item_index = {i: k for k, i in enumerate(item_ids)}
    matrix, students = interaction_matrix(interactions, item_index)
    return Artifact(
        version=version, code_module=module, code_presentation=presentation,
        item_ids=item_ids, item_index=item_index,
        item_type=resources["activity_type"].tolist(),
        item_week=[None if pd.isna(w) else int(w) for w in resources["week_from"]],
        content_sim=content_similarity(resources), cf_sim=item_similarity(matrix),
        popularity=popularity(matrix), n_students=len(students))


def _path(version, module, presentation):
    d = settings.models_dir / version
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{module}_{presentation}.joblib"


def save_artifact(a: Artifact):
    joblib.dump(a, _path(a.version, a.code_module, a.code_presentation), compress=3)


_cache: dict = {}


def load_artifact(version: str, module: str, presentation: str) -> Optional[Artifact]:
    key = (version, module, presentation)
    if key in _cache:
        return _cache[key]
    p = _path(version, module, presentation)
    if not p.exists():
        return None
    _cache[key] = joblib.load(p)
    return _cache[key]


_active = {"version": None, "checked": 0.0}


def active_version(db, ttl=5.0) -> Optional[str]:
    """Cheap cached lookup of the published model version; new versions are picked up within ttl seconds."""
    now = time.time()
    if now - _active["checked"] > ttl:
        doc = db.model_metadata.find_one({"is_active": True}, {"version": 1})
        _active["version"] = doc["version"] if doc else None
        _active["checked"] = now
    return _active["version"]
