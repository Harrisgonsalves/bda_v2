"""Lightweight learner features: updated atomically per event, rebuilt from storage when missing."""
from datetime import datetime, timezone

EVENT_WEIGHTS = {"resource_opened": 1.0, "resource_completed": 3.0,
                 "feedback_useful": 2.0, "feedback_not_useful": 0.0, "search_performed": 0.0}
RESOURCE_EVENTS = {"resource_opened", "resource_completed", "feedback_useful", "feedback_not_useful"}


def rebuild_features(db, student_id: int, module: str, presentation: str) -> dict:
    """Recompute a student's features from historical OULAD rows plus application events."""
    weights, hist_clicks = {}, 0
    for r in db.historical_student_vle.aggregate([
        {"$match": {"id_student": student_id, "code_module": module, "code_presentation": presentation}},
        {"$group": {"_id": "$id_site", "clicks": {"$sum": "$sum_click"}}}]):
        weights[str(r["_id"])] = float(r["clicks"])
        hist_clicks += r["clicks"]
    completed, disliked, type_counts, recent, last = set(), set(), {}, [], None
    total = 0
    q = {"student_id": student_id, "code_module": module, "code_presentation": presentation}
    for e in db.activity_events.find(q).sort("occurred_at", 1):
        total += 1
        t = e["event_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
        rid = e.get("resource_id")
        if rid is not None:
            weights[str(rid)] = weights.get(str(rid), 0.0) + EVENT_WEIGHTS.get(t, 0.0)
            recent.append(rid)
            if t == "resource_completed":
                completed.add(rid)
            if t == "feedback_not_useful":
                disliked.add(rid)
        last = e["occurred_at"]
    doc = {**q, "weights": weights, "completed": sorted(completed), "disliked": sorted(disliked),
           "type_counts": type_counts, "recent": recent[-10:], "total_events": total,
           "historical_clicks": int(hist_clicks), "last_event_at": last,
           "updated_at": datetime.now(timezone.utc)}
    db.learner_features.replace_one(q, doc, upsert=True)
    return doc


def get_features(db, student_id, module, presentation) -> dict:
    doc = db.learner_features.find_one(
        {"student_id": student_id, "code_module": module, "code_presentation": presentation}, {"_id": 0})
    return doc or rebuild_features(db, student_id, module, presentation)


def apply_event(db, ev: dict):
    """Atomic incremental update (no read-modify-write, so concurrent events cannot lose updates)."""
    q = {"student_id": ev["student_id"], "code_module": ev["code_module"],
         "code_presentation": ev["code_presentation"]}
    if not db.learner_features.find_one(q, {"_id": 1}):
        rebuild_features(db, **{"student_id": ev["student_id"], "module": ev["code_module"],
                                "presentation": ev["code_presentation"]})
        return                                   # rebuild already included this event
    t, rid = ev["event_type"], ev.get("resource_id")
    upd = {"$inc": {"total_events": 1, f"type_counts.{t}": 1},
           "$set": {"last_event_at": ev["occurred_at"], "updated_at": datetime.now(timezone.utc)}}
    if rid is not None:
        w = EVENT_WEIGHTS.get(t, 0.0)
        if w:
            upd["$inc"][f"weights.{rid}"] = w
        upd["$push"] = {"recent": {"$each": [rid], "$slice": -10}}
        add = {}
        if t == "resource_completed":
            add["completed"] = rid
        if t == "feedback_not_useful":
            add["disliked"] = rid
        if add:
            upd["$addToSet"] = add
    db.learner_features.update_one(q, upd)
