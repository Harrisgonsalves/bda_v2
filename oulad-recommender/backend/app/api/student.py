from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_student
from app.db.mongodb import get_db
from app.models.schemas import EventBatch, EventIn, FeedbackIn
from app.services import activity_service as act, feature_service as fs
from app.services import recommendation_service as recs, resource_service as res

router = APIRouter(prefix="/student", tags=["student"])


def _course(db, sid, module, presentation):
    """Pick the requested enrolled course, or the student's most recent presentation."""
    q = {"id_student": sid}
    if module and presentation:
        q.update(code_module=module, code_presentation=presentation)
    row = db.students.find_one(q, {"_id": 0}, sort=[("code_presentation", -1)])
    if not row:
        raise HTTPException(404, "Course presentation not found for this student")
    return row["code_module"], row["code_presentation"]


@router.get("/profile")
def profile(user=Depends(current_student)):
    db = get_db()
    rows = list(db.students.find({"id_student": user["student_id"]}, {"_id": 0}))
    return {"student_id": user["student_id"], "email": user["email"], "enrolments": rows}


@router.get("/courses")
def courses(user=Depends(current_student)):
    db = get_db()
    out = []
    for s in db.students.find({"id_student": user["student_id"]}, {"_id": 0}).sort("code_presentation", -1):
        c = db.courses.find_one({"code_module": s["code_module"], "code_presentation": s["code_presentation"]},
                                {"_id": 0}) or {}
        out.append({**c, "final_result": s.get("final_result")})
    return out


@router.get("/resources")
def resources(code_module: Optional[str] = None, code_presentation: Optional[str] = None,
              q: Optional[str] = None, activity_type: Optional[str] = None,
              skip: int = Query(0, ge=0), limit: int = Query(24, ge=1, le=100), user=Depends(current_student)):
    db = get_db()
    m, p = _course(db, user["student_id"], code_module, code_presentation)
    out = res.search_resources(db, m, p, q, activity_type, skip, limit)
    out["activity_types"] = res.activity_types(db, m, p)
    out["code_module"], out["code_presentation"] = m, p
    return out


@router.get("/recommendations")
def recommendations(code_module: Optional[str] = None, code_presentation: Optional[str] = None,
                    limit: int = Query(10, ge=1, le=20), user=Depends(current_student)):
    db = get_db()
    m, p = _course(db, user["student_id"], code_module, code_presentation)
    items = recs.get_or_refresh(db, user["student_id"], m, p)
    if items is None:
        return {"code_module": m, "code_presentation": p, "ready": False, "items": []}
    return {"code_module": m, "code_presentation": p, "ready": True, "items": items[:limit],
            "model_version": items[0]["model_version"] if items else None}


@router.get("/activity")
def activity(code_module: Optional[str] = None, code_presentation: Optional[str] = None,
             limit: int = Query(20, ge=1, le=100), user=Depends(current_student)):
    return act.recent_activity(get_db(), user["student_id"], limit, code_module, code_presentation)


@router.get("/progress")
def progress(code_module: Optional[str] = None, code_presentation: Optional[str] = None,
             user=Depends(current_student)):
    db = get_db()
    m, p = _course(db, user["student_id"], code_module, code_presentation)
    f = fs.get_features(db, user["student_id"], m, p)
    total_res = db.resources.count_documents({"code_module": m, "code_presentation": p})
    return {"code_module": m, "code_presentation": p, "resources_total": total_res,
            "resources_touched": sum(1 for v in f["weights"].values() if v > 0),
            "resources_completed": len(f.get("completed", [])),
            "historical_clicks": f.get("historical_clicks", 0),
            "app_events": f.get("total_events", 0), "type_counts": f.get("type_counts", {}),
            "last_event_at": f.get("last_event_at")}


@router.post("/events", status_code=202)
def post_event(body: EventIn, user=Depends(current_student)):
    db = get_db()
    ev, dup = act.record_event(db, user["student_id"], body.model_dump())
    updated = None
    if not dup and body.event_type != "search_performed":
        updated = recs.refresh(db, user["student_id"], body.code_module, body.code_presentation)
    return {"accepted": True, "duplicate": dup, "event_id": ev["event_id"],
            "recommendations_refreshed": updated is not None,
            "recommendations": updated[:10] if updated else None}


@router.post("/events/batch", status_code=202)
def post_batch(body: EventBatch, user=Depends(current_student)):
    db = get_db()
    accepted = dups = 0
    touched = set()
    for e in body.events:
        _, dup = act.record_event(db, user["student_id"], e.model_dump())
        dups += dup
        accepted += not dup
        touched.add((e.code_module, e.code_presentation))
    for m, p in touched:                    # one refresh per course, not per event
        recs.refresh(db, user["student_id"], m, p)
    return {"accepted": accepted, "duplicates": dups}


@router.post("/recommendations/feedback", status_code=202)
def feedback(body: FeedbackIn, user=Depends(current_student)):
    db = get_db()
    ev = EventIn(event_type="feedback_useful" if body.useful else "feedback_not_useful",
                 resource_id=body.resource_id, code_module=body.code_module,
                 code_presentation=body.code_presentation, client_event_id=body.client_event_id)
    e, dup = act.record_event(db, user["student_id"], ev.model_dump())
    updated = None if dup else recs.refresh(db, user["student_id"], body.code_module, body.code_presentation)
    return {"accepted": True, "duplicate": dup, "recommendations": updated[:10] if updated else None}
