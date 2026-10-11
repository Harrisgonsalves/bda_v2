from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.core.config import settings


def overview(db):
    s = lambda k: (db.analytics_summaries.find_one({"key": k}) or {}).get("data")
    return {
        "students": db.students.estimated_document_count(),
        "accounts": db.users.count_documents({"role": "student"}),
        "resources": db.resources.estimated_document_count(),
        "historical_rows": db.historical_student_vle.estimated_document_count(),
        "app_events": db.activity_events.estimated_document_count(),
        "synthetic_events": db.activity_events.count_documents({"source": "synthetic"}),
        "recommendations": db.recommendations.estimated_document_count(),
        "feedback_total": db.activity_events.count_documents(
            {"event_type": {"$in": ["feedback_useful", "feedback_not_useful"]}}),
        "course_summaries_ready": s("course_summaries") is not None}


def activity_trend(db, days: int = 30):
    if days > settings.max_range_days or days < 1:
        raise HTTPException(422, f"days must be between 1 and {settings.max_range_days}")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pipe = [{"$match": {"occurred_at": {"$gte": since}}},
            {"$group": {"_id": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$occurred_at"}},
                                "type": "$event_type"}, "n": {"$sum": 1}}},
            {"$sort": {"_id.day": 1}}]
    by_day = {}
    for r in db.activity_events.aggregate(pipe, allowDiskUse=True):
        by_day.setdefault(r["_id"]["day"], {"day": r["_id"]["day"]})[r["_id"]["type"]] = r["n"]
    return list(by_day.values())


def popular_resources(db, module=None, presentation=None, limit=15):
    """Popularity from application events (live) ..."""
    match = {"resource_id": {"$ne": None}}
    if module:
        match["code_module"] = module
    if presentation:
        match["code_presentation"] = presentation
    pipe = [{"$match": match},
            {"$group": {"_id": {"id": "$resource_id", "m": "$code_module", "p": "$code_presentation"},
                        "events": {"$sum": 1}}},
            {"$sort": {"events": -1}}, {"$limit": limit}]
    return [{"resource_id": r["_id"]["id"], "code_module": r["_id"]["m"],
             "code_presentation": r["_id"]["p"], "events": r["events"]}
            for r in db.activity_events.aggregate(pipe, allowDiskUse=True)]


def recommendation_stats(db):
    useful = db.activity_events.count_documents({"event_type": "feedback_useful"})
    not_useful = db.activity_events.count_documents({"event_type": "feedback_not_useful"})
    with_recs = len(db.recommendations.distinct("student_id"))
    accounts = db.users.count_documents({"role": "student"})
    return {"students_with_recommendations": with_recs, "student_accounts": accounts,
            "coverage": round(with_recs / accounts, 3) if accounts else 0,
            "useful": useful, "not_useful": not_useful,
            "useful_rate": round(useful / (useful + not_useful), 3) if useful + not_useful else None}
