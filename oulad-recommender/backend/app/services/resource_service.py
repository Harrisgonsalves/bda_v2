import re


def search_resources(db, module, presentation, q=None, activity_type=None, skip=0, limit=24):
    flt = {"code_module": module, "code_presentation": presentation}
    if activity_type:
        flt["activity_type"] = activity_type
    if q:
        flt["title"] = {"$regex": re.escape(q), "$options": "i"}
    total = db.resources.count_documents(flt)
    items = list(db.resources.find(flt, {"_id": 0}).sort("id_site", 1).skip(skip).limit(limit))
    return {"total": total, "items": items}


def activity_types(db, module, presentation):
    return sorted(db.resources.distinct("activity_type", {"code_module": module, "code_presentation": presentation}))
