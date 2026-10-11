import json
import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.security import current_admin
from app.db.mongodb import get_db
from app.services import analytics_service as an, feature_service as fs

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(current_admin)])
JOB_TYPES = {"recommendations": "rebuild_recommendations", "analytics": "rebuild_analytics",
             "clustering": "run_clustering", "network": "run_network_analysis"}


def _summary(key):
    d = get_db().analytics_summaries.find_one({"key": key}, {"_id": 0})
    return d["data"] if d else None


@router.get("/overview")
def overview():
    return an.overview(get_db())


@router.get("/students")
def students(q: Optional[str] = None, skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    db = get_db()
    flt = {"role": "student"}
    if q:
        flt["$or"] = [{"email": {"$regex": re.escape(q), "$options": "i"}}]
        if q.isdigit():
            flt["$or"].append({"student_id": int(q)})
    items = list(db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("student_id", 1).skip(skip).limit(limit))
    return {"total": db.users.count_documents(flt), "items": items}


@router.get("/students/{student_id}")
def student_detail(student_id: int, limit: int = Query(30, ge=1, le=100)):
    db = get_db()
    enr = list(db.students.find({"id_student": student_id}, {"_id": 0}))
    if not enr:
        raise HTTPException(404, "Student not found")
    feats = list(db.learner_features.find({"student_id": student_id}, {"_id": 0, "weights": 0}))
    events = list(db.activity_events.find({"student_id": student_id}, {"_id": 0})
                  .sort("occurred_at", -1).limit(limit))
    return {"student_id": student_id, "enrolments": enr, "features": feats, "recent_events": events}


@router.get("/courses")
def courses():
    summ = _summary("course_summaries")
    if summ is not None:
        return summ
    return list(get_db().courses.find({}, {"_id": 0}))   # fallback until the analytics job has run


@router.get("/resources/popular")
def popular(code_module: Optional[str] = None, code_presentation: Optional[str] = None,
            limit: int = Query(15, ge=1, le=50)):
    return {"live": an.popular_resources(get_db(), code_module, code_presentation, limit),
            "historical": (_summary("popular_historical") or [])[:limit]}


@router.get("/analytics/activity")
def activity(days: int = Query(30, ge=1, le=365)):
    return an.activity_trend(get_db(), days)


@router.get("/analytics/recommendations")
def rec_analytics():
    return an.recommendation_stats(get_db())


@router.get("/analytics/clusters")
def clusters():
    return _summary("clusters") or {}


def _enqueue(kind, params=None):
    db = get_db()
    if db.job_runs.find_one({"job_type": JOB_TYPES[kind], "status": {"$in": ["pending", "running"]}}):
        raise HTTPException(409, "A job of this type is already queued or running")
    job = {"job_type": JOB_TYPES[kind], "status": "pending", "attempts": 0, "max_attempts": 3,
           "created_at": datetime.now(timezone.utc), "started_at": None, "finished_at": None,
           "processed": 0, "error": None, "model_version": None, "params": params}
    r = db.job_runs.insert_one(job)
    return {"job_id": str(r.inserted_id), "status": "pending", "job_type": job["job_type"]}


@router.post("/jobs/recommendations/rebuild", status_code=202)
def rebuild_recs():
    return _enqueue("recommendations")


@router.post("/jobs/analytics/rebuild", status_code=202)
def rebuild_analytics():
    return _enqueue("analytics")


@router.post("/jobs/clustering/run", status_code=202)
def run_clustering():
    return _enqueue("clustering")


class NetworkIn(BaseModel):
    code_module: str
    code_presentation: str
    max_students: int = Field(40, ge=5, le=80)


@router.post("/jobs/network/run", status_code=202)
def run_network(body: NetworkIn):
    return _enqueue("network", body.model_dump())


@router.get("/network/meta")
def network_meta():
    f = settings.static_dir / "network" / "communities.json"
    return json.loads(f.read_text()) if f.exists() else {}


@router.get("/jobs")
def jobs(limit: int = Query(20, ge=1, le=100)):
    out = []
    for j in get_db().job_runs.find({}).sort("created_at", -1).limit(limit):
        j["job_id"] = str(j.pop("_id"))
        out.append(j)
    return out


@router.get("/models/current")
def current_model():
    m = get_db().model_metadata.find_one({"is_active": True}, {"_id": 0})
    return m or {"version": None, "message": "No model published yet. Run the recommendation rebuild job."}
