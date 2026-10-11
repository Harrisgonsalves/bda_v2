import os
import subprocess
import time
from datetime import datetime, timezone
import pandas as pd
from app.core.config import settings
from app.db.mongodb import get_db
from app.processing import aggregation as agg
from app.processing.clustering import cluster_learners
from app.recommender import artifacts, hybrid
from app.services import feature_service as fs, recommendation_service as recsvc


def _courses(db):
    return [(c["code_module"], c["code_presentation"]) for c in db.courses.find({}, {"_id": 0})]


def _interactions(db, module, pres, event_pairs) -> pd.DataFrame:
    rows = []
    for r in db.historical_student_vle.aggregate([
        {"$match": {"code_module": module, "code_presentation": pres}},
        {"$group": {"_id": {"s": "$id_student", "i": "$id_site"}, "w": {"$sum": "$sum_click"}}}],
            allowDiskUse=True):
        rows.append((r["_id"]["s"], r["_id"]["i"], r["w"]))
    for (m, p, s, i), w in event_pairs.items():
        if m == module and p == pres:
            rows.append((s, i, w))
    return pd.DataFrame(rows, columns=["student", "item", "weight"])


def rebuild_recommendations(db, job):
    t0 = time.time()
    version = "v" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    # MapReduce-style: application events -> (course, student, resource) weight totals
    events = db.activity_events.find({}, {"_id": 0, "event_type": 1, "resource_id": 1, "student_id": 1,
                                          "code_module": 1, "code_presentation": 1})
    pairs = agg.map_reduce(events, agg.event_weight_mapper(fs.EVENT_WEIGHTS))
    built = 0
    for module, pres in _courses(db):
        res = pd.DataFrame(list(db.resources.find({"code_module": module, "code_presentation": pres},
                                                  {"_id": 0})))
        if res.empty:
            continue
        art = artifacts.build_artifact(version, module, pres, res, _interactions(db, module, pres, pairs))
        artifacts.save_artifact(art)
        built += 1
        db.job_runs.update_one({"_id": job["_id"]}, {"$set": {"processed": built}})
    # bulk-refresh recommendations for every student that has features, under the NEW version
    n = 0
    for u in db.users.find({"role": "student"}, {"student_id": 1}):
        for e in db.students.find({"id_student": u["student_id"]}, {"code_module": 1, "code_presentation": 1}):
            art = artifacts.load_artifact(version, e["code_module"], e["code_presentation"])
            if art is None:
                continue
            f = fs.get_features(db, u["student_id"], e["code_module"], e["code_presentation"])
            ex = {int(k) for k, v in f["weights"].items() if v > 0} | set(f.get("completed", [])) | set(f.get("disliked", []))
            recsvc.store(db, u["student_id"], e["code_module"], e["code_presentation"], version,
                         hybrid.recommend(art, f["weights"], ex, settings.alpha, settings.top_k_store))
            n += 1
    # publish only after everything above succeeded
    db.model_metadata.update_many({}, {"$set": {"is_active": False}})
    db.model_metadata.insert_one({
        "version": version, "is_active": True, "trained_at": datetime.now(timezone.utc),
        "training_seconds": round(time.time() - t0, 2), "courses_built": built, "students_refreshed": n,
        "event_pairs": len(pairs), "alpha": settings.alpha,
        "dataset": {"historical_rows": db.historical_student_vle.estimated_document_count(),
                    "app_events": db.activity_events.estimated_document_count()},
        "features": {"content": "TF-IDF(activity_type, module, week bucket)",
                     "collaborative": "item-based cosine on log1p(clicks)"}})
    db.recommendations.delete_many({"model_version": {"$ne": version}})
    db.job_runs.update_one({"_id": job["_id"]}, {"$set": {"model_version": version, "processed": built}})
    artifacts._active["checked"] = 0


def rebuild_analytics(db, job):
    now = datetime.now(timezone.utc)
    clicks = {}
    for r in db.historical_student_vle.aggregate([
        {"$group": {"_id": {"m": "$code_module", "p": "$code_presentation"},
                    "clicks": {"$sum": "$sum_click"}, "rows": {"$sum": 1}}}], allowDiskUse=True):
        clicks[(r["_id"]["m"], r["_id"]["p"])] = r
    summaries = []
    for c in db.courses.find({}, {"_id": 0}):
        k = (c["code_module"], c["code_presentation"])
        q = {"code_module": k[0], "code_presentation": k[1]}
        mix = {r["_id"]: r["n"] for r in db.students.aggregate(
            [{"$match": q}, {"$group": {"_id": "$final_result", "n": {"$sum": 1}}}])}
        summaries.append({**c, "students": sum(mix.values()), "final_result_mix": mix,
                          "resources": db.resources.count_documents(q),
                          "historical_clicks": clicks.get(k, {}).get("clicks", 0),
                          "app_events": db.activity_events.count_documents(q)})
    pop = []
    for r in db.historical_student_vle.aggregate([
        {"$group": {"_id": {"i": "$id_site", "m": "$code_module", "p": "$code_presentation"},
                    "clicks": {"$sum": "$sum_click"}}},
        {"$sort": {"clicks": -1}}, {"$limit": 50}], allowDiskUse=True):
        meta = db.resources.find_one({"id_site": r["_id"]["i"], "code_module": r["_id"]["m"],
                                      "code_presentation": r["_id"]["p"]}, {"_id": 0}) or {}
        pop.append({"resource_id": r["_id"]["i"], "code_module": r["_id"]["m"],
                    "code_presentation": r["_id"]["p"], "clicks": r["clicks"],
                    "activity_type": meta.get("activity_type"), "title": meta.get("title")})
    for key, data in (("course_summaries", summaries), ("popular_historical", pop)):
        db.analytics_summaries.update_one({"key": key}, {"$set": {"data": data, "updated_at": now}}, upsert=True)
    db.job_runs.update_one({"_id": job["_id"]}, {"$set": {"processed": len(summaries)}})


def run_clustering(db, job):
    rows = list(db.historical_student_vle.aggregate([
        {"$group": {"_id": {"s": "$id_student", "m": "$code_module", "p": "$code_presentation"},
                    "total_clicks": {"$sum": "$sum_click"}, "active_rows": {"$sum": 1}}},
        {"$sample": {"size": 50000}}], allowDiskUse=True))
    if len(rows) < 20:
        raise RuntimeError("Not enough historical data to cluster")
    df = pd.DataFrame([{"s": r["_id"]["s"], "m": r["_id"]["m"], "p": r["_id"]["p"],
                        "total_clicks": r["total_clicks"], "active_rows": r["active_rows"]} for r in rows])
    fr = {(r["id_student"], r["code_module"], r["code_presentation"]): r.get("final_result")
          for r in db.students.find({"id_student": {"$in": df["s"].unique().tolist()}},
                                    {"id_student": 1, "code_module": 1, "code_presentation": 1, "final_result": 1})}
    df["final_result"] = [fr.get((s, m, p)) for s, m, p in zip(df["s"], df["m"], df["p"])]
    summary, _ = cluster_learners(df, k=4)
    db.analytics_summaries.update_one({"key": "clusters"}, {"$set": {
        "data": {"k": 4, "sample_size": len(df), "clusters": summary}, "updated_at": datetime.now(timezone.utc)}},
        upsert=True)
    db.job_runs.update_one({"_id": job["_id"]}, {"$set": {"processed": len(df)}})


def run_network(db, job):
    """Calls the R script that builds the community graph from stored recommendations."""
    from app.core.config import ROOT
    p = job.get("params") or {}
    out = settings.static_dir / "network"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [settings.rscript, str(ROOT / "r" / "community_network.R"), settings.mongo_uri, settings.mongo_db,
           p["code_module"], p["code_presentation"], str(int(p.get("max_students", 40))), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-400:])
    db.job_runs.update_one({"_id": job["_id"]}, {"$set": {"processed": int(p.get("max_students", 40))}})


HANDLERS = {"run_network_analysis": run_network, "rebuild_recommendations": rebuild_recommendations, "rebuild_analytics": rebuild_analytics,
            "run_clustering": run_clustering}
