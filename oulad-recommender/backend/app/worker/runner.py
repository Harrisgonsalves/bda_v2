"""Separate worker process:  python -m app.worker.runner"""
import time
import traceback
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from app.db.indexes import create_indexes
from app.db.mongodb import get_db
from app.worker.jobs import HANDLERS

STALE_AFTER = timedelta(minutes=30)


def claim(db):
    """Atomic claim so two workers can never run the same job."""
    return db.job_runs.find_one_and_update(
        {"status": "pending"}, {"$set": {"status": "running", "started_at": datetime.now(timezone.utc)},
                                "$inc": {"attempts": 1}},
        sort=[("created_at", 1)], return_document=ReturnDocument.AFTER)


def requeue_stale(db):
    db.job_runs.update_many({"status": "running", "started_at": {"$lt": datetime.now(timezone.utc) - STALE_AFTER}},
                            {"$set": {"status": "pending"}})


def main():
    create_indexes()
    db = get_db()
    print("Worker started. Waiting for jobs...")
    while True:
        requeue_stale(db)
        job = claim(db)
        if not job:
            time.sleep(3)
            continue
        print(f"Running {job['job_type']} (attempt {job['attempts']})")
        try:
            HANDLERS[job["job_type"]](db, job)
            db.job_runs.update_one({"_id": job["_id"]}, {"$set": {
                "status": "succeeded", "finished_at": datetime.now(timezone.utc), "error": None}})
        except Exception as exc:   # failed jobs are retried safely: handlers publish only on success
            traceback.print_exc()
            status = "pending" if job["attempts"] < job.get("max_attempts", 3) else "failed"
            db.job_runs.update_one({"_id": job["_id"]}, {"$set": {
                "status": status, "error": str(exc)[:500], "finished_at": datetime.now(timezone.utc)}})
            time.sleep(2)


if __name__ == "__main__":
    main()
