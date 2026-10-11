"""Create the admin account and demo student logins linked to real OULAD learners.
   python scripts/create_users.py --count 200"""
import argparse
import _common  # noqa
from datetime import datetime, timezone
from app.core.security import hash_password
from app.db.indexes import create_indexes
from app.db.mongodb import get_db


def upsert(db, user):
    db.users.update_one({"email": user["email"]}, {"$set": user, "$setOnInsert": {
        "created_at": datetime.now(timezone.utc)}}, upsert=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--student-password", default="student123")
    ap.add_argument("--admin-password", default="admin123")
    a = ap.parse_args()
    db = get_db()
    create_indexes()
    upsert(db, {"user_id": "u_admin", "email": "admin@demo.edu", "role": "admin", "student_id": None,
                "is_active": True, "password_hash": hash_password(a.admin_password)})
    pw = hash_password(a.student_password)   # hash once; the same demo password for all demo students
    have = set(db.users.distinct("student_id"))
    made = 0
    for row in db.students.aggregate([{"$group": {"_id": "$id_student"}}, {"$sample": {"size": a.count * 3}}]):
        sid = row["_id"]
        if sid in have or not db.historical_student_vle.find_one({"id_student": sid}, {"_id": 1}):
            continue                       # only learners that actually have VLE history
        upsert(db, {"user_id": f"u_{sid}", "email": f"student{sid}@demo.edu", "role": "student",
                    "student_id": int(sid), "is_active": True, "password_hash": pw})
        made += 1
        if made >= a.count - len([h for h in have if h]):
            break
    total = db.users.count_documents({"role": "student"})
    print(f"Student accounts: {total}. Admin: admin@demo.edu / {a.admin_password}")
    for u in db.users.find({"role": "student"}, {"email": 1}).limit(5):
        print(f"  e.g. {u['email']} / {a.student_password}")


if __name__ == "__main__":
    main()
