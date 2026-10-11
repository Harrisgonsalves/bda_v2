"""Generate labelled synthetic application events (source='synthetic'). Deterministic for a given seed.
   python scripts/generate_activity.py --events 100000"""
import argparse
import json
import time
import _common  # noqa
from datetime import datetime, timedelta, timezone
import numpy as np
from pymongo.errors import BulkWriteError
from app.db.mongodb import get_db
from app.core.config import ROOT

TYPES = ["resource_opened", "resource_completed", "search_performed", "feedback_useful", "feedback_not_useful"]
P = [0.72, 0.15, 0.06, 0.04, 0.03]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=100_000)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    db = get_db()
    accounts = [u["student_id"] for u in db.users.find({"role": "student"}, {"student_id": 1})]
    if not accounts:
        raise SystemExit("No student accounts. Run scripts/create_users.py first.")
    # one course per student (their latest presentation) and a personal "attention set" of resources
    plan, res_cache = [], {}
    for sid in accounts:
        row = db.students.find_one({"id_student": sid}, sort=[("code_presentation", -1)])
        key = (row["code_module"], row["code_presentation"])
        if key not in res_cache:
            res_cache[key] = list(db.resources.find({"code_module": key[0], "code_presentation": key[1]},
                                                     {"id_site": 1, "activity_type": 1}))
        rs = res_cache[key]
        if not rs:
            continue
        n = len(rs)
        base = 1.0 / np.arange(1, n + 1) ** 0.8                       # popularity skew
        pref = rng.choice(sorted({r["activity_type"] for r in rs}), size=min(2, len({r["activity_type"] for r in rs})), replace=False)
        w = base[rng.permutation(n)] * np.array([3.0 if r["activity_type"] in pref else 1.0 for r in rs])
        pick = rng.choice(n, size=min(60, n), replace=False, p=w / w.sum())
        plan.append((sid, key, [rs[i]["id_site"] for i in pick]))
    now = datetime.now(timezone.utc)
    t0, batch, written = time.time(), [], 0
    owners = rng.integers(0, len(plan), a.events)
    kinds = rng.choice(len(TYPES), a.events, p=P)
    secs = rng.integers(0, a.days * 86400, a.events)
    for i in range(a.events):
        sid, (m, p), items = plan[owners[i]]
        t = TYPES[kinds[i]]
        batch.append({"event_id": f"evt_syn{a.seed}_{i:07d}", "student_id": int(sid), "source": "synthetic",
                      "event_type": t, "resource_id": None if t == "search_performed" else int(items[rng.integers(0, len(items))]),
                      "code_module": m, "code_presentation": p, "occurred_at": now - timedelta(seconds=int(secs[i])),
                      "metadata": {"generator_seed": a.seed}})
        if len(batch) >= 5000 or i == a.events - 1:
            try:
                written += len(db.activity_events.insert_many(batch, ordered=False).inserted_ids)
            except BulkWriteError as e:             # re-running with the same seed skips existing events
                written += e.details["nInserted"]
            batch = []
    secs_taken = time.time() - t0
    # features/recommendations for these students are rebuilt lazily from the stored events
    db.learner_features.delete_many({"student_id": {"$in": accounts}})
    db.recommendations.delete_many({"student_id": {"$in": accounts}})
    manifest = {"generated_at": now.isoformat(), "seed": a.seed, "requested": a.events, "inserted": written,
                "students": len(plan), "insert_seconds": round(secs_taken, 2),
                "events_per_second": round(written / max(secs_taken, 1e-9))}
    out = ROOT / "data" / "synthetic" / f"manifest_seed{a.seed}.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
