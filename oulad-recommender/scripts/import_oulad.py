"""Import OULAD CSVs into MongoDB. Safe to re-run.
   python scripts/import_oulad.py --data-dir data/raw [--sample-students 8000] [--reset-vle]"""
import argparse
import _common  # noqa
from pathlib import Path
import numpy as np
import pandas as pd


def rd(path, **kw):
    return pd.read_csv(path, na_values=["?"], **kw)   # OULAD marks missing values with "?"
from app.db.indexes import create_indexes
from app.db.mongodb import get_db


def clean(df: pd.DataFrame) -> list:
    return df.astype(object).where(df.notna(), None).to_dict("records")


def reload(db, name, df):
    """Small tables: replace contents, so re-running never duplicates rows."""
    db[name].delete_many({})
    recs = clean(df)
    for i in range(0, len(recs), 20000):
        db[name].insert_many(recs[i:i + 20000], ordered=False)
    print(f"  {name}: {len(recs)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--sample-students", type=int, default=0, help="import only N random students (0 = all)")
    ap.add_argument("--reset-vle", action="store_true", help="drop and reload historical_student_vle")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    d, db = Path(a.data_dir), get_db()

    info = rd(d / "studentInfo.csv")
    keep = None
    if a.sample_students:
        ids = info["id_student"].drop_duplicates()
        keep = set(ids.sample(min(a.sample_students, len(ids)), random_state=a.seed))
        print(f"Sampling {len(keep)} students")
    filt = (lambda df: df[df["id_student"].isin(keep)]) if keep else (lambda df: df)

    print("Importing reference tables")
    courses = rd(d / "courses.csv")
    courses = courses.rename(columns={"length": "module_presentation_length"})
    reload(db, "courses", courses)
    vle = rd(d / "vle.csv")
    vle["title"] = vle["activity_type"].str.replace("_", " ").str.title() + " " + vle["id_site"].astype(str)
    vle["url"] = "/resources/" + vle["id_site"].astype(str)
    reload(db, "resources", vle)
    reload(db, "assessments", rd(d / "assessments.csv"))
    reload(db, "students", filt(info))
    reload(db, "student_registrations", filt(rd(d / "studentRegistration.csv")))
    reload(db, "student_assessments", filt(rd(d / "studentAssessment.csv")))

    if db.historical_student_vle.estimated_document_count() and not a.reset_vle:
        print("historical_student_vle already populated; use --reset-vle to reload. Skipping.")
    else:
        db.historical_student_vle.drop()
        total = 0
        print("Importing studentVle.csv in chunks (this is the large file)")
        for chunk in rd(d / "studentVle.csv", chunksize=200_000):
            chunk = filt(chunk)
            if len(chunk):
                db.historical_student_vle.insert_many(clean(chunk), ordered=False)
                total += len(chunk)
                print(f"  {total:,} rows", end="\r")
        print(f"\n  historical_student_vle: {total:,} rows")
    create_indexes()
    print("Indexes created. Import complete.")


if __name__ == "__main__":
    main()
