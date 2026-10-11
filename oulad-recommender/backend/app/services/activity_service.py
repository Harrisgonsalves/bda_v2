import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.services import feature_service as fs


def make_event_id(student_id: int, client_event_id: str | None) -> str:
    """Deterministic when the client supplies an id, so a retry maps to the same event."""
    if client_event_id:
        return "evt_" + hashlib.sha1(f"{student_id}:{client_event_id}".encode()).hexdigest()[:16]
    return "evt_" + uuid.uuid4().hex[:16]


def validate_event(db, student_id: int, p: dict):
    if not db.students.find_one({"id_student": student_id, "code_module": p["code_module"],
                                 "code_presentation": p["code_presentation"]}, {"_id": 1}):
        raise HTTPException(403, "You are not enrolled in this course presentation")
    if p["event_type"] in fs.RESOURCE_EVENTS:
        if p.get("resource_id") is None:
            raise HTTPException(422, "resource_id is required for this event type")
        if not db.resources.find_one({"id_site": p["resource_id"], "code_module": p["code_module"],
                                      "code_presentation": p["code_presentation"]}, {"_id": 1}):
            raise HTTPException(404, "Resource not found in this course presentation")


def record_event(db, student_id: int, p: dict, source: str = "application"):
    """Returns (event, duplicate). Features are only touched for newly inserted events."""
    validate_event(db, student_id, p)
    ev = {"event_id": make_event_id(student_id, p.get("client_event_id")),
          "student_id": student_id, "source": source, "event_type": p["event_type"],
          "resource_id": p.get("resource_id"), "code_module": p["code_module"],
          "code_presentation": p["code_presentation"], "occurred_at": datetime.now(timezone.utc),
          "metadata": {**(p.get("metadata") or {}), "client_event_id": p.get("client_event_id")}}
    if p.get("query"):
        ev["metadata"]["query"] = p["query"][:200]
    try:
        db.activity_events.insert_one(dict(ev))
    except DuplicateKeyError:
        return ev, True
    fs.apply_event(db, ev)
    return ev, False


def recent_activity(db, student_id: int, limit: int = 20, module=None, presentation=None):
    q = {"student_id": student_id}
    if module:
        q["code_module"] = module
    if presentation:
        q["code_presentation"] = presentation
    return list(db.activity_events.find(q, {"_id": 0}).sort("occurred_at", -1).limit(limit))
