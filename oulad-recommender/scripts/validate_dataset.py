"""Check the OULAD CSVs before importing.   python scripts/validate_dataset.py --data-dir data/raw"""
import argparse
import _common  # noqa
from pathlib import Path
import pandas as pd

FILES = {
    "courses.csv": ["code_module", "code_presentation", "module_presentation_length"],
    "assessments.csv": ["code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"],
    "vle.csv": ["id_site", "code_module", "code_presentation", "activity_type", "week_from", "week_to"],
    "studentInfo.csv": ["code_module", "code_presentation", "id_student", "gender", "region", "highest_education",
                        "imd_band", "age_band", "num_of_prev_attempts", "studied_credits", "disability", "final_result"],
    "studentRegistration.csv": ["code_module", "code_presentation", "id_student", "date_registration", "date_unregistration"],
    "studentAssessment.csv": ["id_assessment", "id_student", "date_submitted", "is_banked", "score"],
    "studentVle.csv": ["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw")
    d = Path(ap.parse_args().data_dir)
    ok = True
    for name, cols in FILES.items():
        p = d / name
        if not p.exists():
            print(f"MISSING  {name}"); ok = False; continue
        head = pd.read_csv(p, nrows=5)
        # courses.csv uses "length" in some releases; the importer maps it
        missing = [c for c in cols if c not in head.columns and not (c == "module_presentation_length" and "length" in head.columns)]
        print(("OK       " if not missing else "COLUMNS  ") + name + (f" missing {missing}" if missing else ""))
        ok &= not missing
    if not ok:
        raise SystemExit("Fix the problems above before importing.")
    vle = pd.read_csv(d / "vle.csv")
    dup = vle.duplicated(["id_site", "code_module", "code_presentation"]).sum()
    print(f"vle.csv: {len(vle)} rows, {dup} duplicate (id_site, module, presentation) keys")
    sv = pd.read_csv(d / "studentVle.csv", usecols=["code_module", "code_presentation", "id_student", "id_site", "date"])
    print(f"studentVle.csv: {len(sv)} rows")
    k = ["id_student", "id_site", "code_module", "code_presentation", "date"]
    print(f"  duplicate student/site/day rows (kept as separate rows): {sv.duplicated(k).sum()}")
    keys = set(map(tuple, vle[["id_site", "code_module", "code_presentation"]].to_numpy()))
    orphan = ~pd.Series(list(zip(sv.id_site, sv.code_module, sv.code_presentation))).isin(keys)
    print(f"  rows whose resource is missing from vle.csv: {int(orphan.sum())}")
    print("Validation finished.")


if __name__ == "__main__":
    main()
