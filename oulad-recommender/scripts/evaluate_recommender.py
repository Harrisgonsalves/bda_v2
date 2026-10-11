"""Time-split offline evaluation: content-only vs collaborative-only vs hybrid vs popularity.
Training uses only interactions up to a cutoff day; the test set is resources first used AFTER it,
so no future interaction leaks into the model.
   python scripts/evaluate_recommender.py --data-dir data/raw --module AAA --presentation 2014J"""
import argparse
import math
import _common  # noqa
from pathlib import Path
import numpy as np
import pandas as pd


def rd(path, **kw):
    return pd.read_csv(path, na_values=["?"], **kw)   # OULAD marks missing values with "?"
from app.recommender.artifacts import build_artifact
from app.recommender.hybrid import recommend
from app.core.config import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--module", default="AAA")
    ap.add_argument("--presentation", default="2014J")
    ap.add_argument("--cutoff-quantile", type=float, default=0.7)
    ap.add_argument("--max-students", type=int, default=1000)
    ap.add_argument("--k", type=int, default=10)
    a = ap.parse_args()
    d = Path(a.data_dir)
    vle = rd(d / "vle.csv")
    vle = vle[(vle.code_module == a.module) & (vle.code_presentation == a.presentation)]
    sv = rd(d / "studentVle.csv")
    sv = sv[(sv.code_module == a.module) & (sv.code_presentation == a.presentation)]
    cutoff = sv["date"].quantile(a.cutoff_quantile)
    train, future = sv[sv["date"] <= cutoff], sv[sv["date"] > cutoff]
    tr = train.groupby(["id_student", "id_site"], as_index=False)["sum_click"].sum()
    tr.columns = ["student", "item", "weight"]
    art = build_artifact("eval", a.module, a.presentation, vle, tr)       # trained on the past only
    seen = tr.groupby("student")["item"].apply(set).to_dict()
    wts = {s: dict(zip(g["item"], g["weight"])) for s, g in tr.groupby("student")}
    test = {s: set(g["id_site"]) - seen.get(s, set()) for s, g in future.groupby("id_student")}
    users = [s for s, t in test.items() if t and len(seen.get(s, ())) >= 5]
    rng = np.random.default_rng(0)
    if len(users) > a.max_students:
        users = list(rng.choice(users, a.max_students, replace=False))
    print(f"{a.module} {a.presentation}: cutoff day {cutoff:.0f}, evaluating {len(users)} students, k={a.k}")
    rows = []
    for name, mode, alpha in [("popularity (cold-start baseline)", "pop", 0.5), ("content-only", "content", 0.5),
                              ("collaborative-only", "collaborative", 0.5), ("hybrid a=0.5", "hybrid", 0.5),
                              ("hybrid a=0.3", "hybrid", 0.3), ("hybrid a=0.7", "hybrid", 0.7)]:
        P = R = H = N = 0.0
        for s in users:
            w = {} if mode == "pop" else wts[s]
            recs = recommend(art, w, seen[s], alpha, a.k, "hybrid" if mode == "pop" else mode)
            ids = [r["resource_id"] for r in recs]
            hits = [i in test[s] for i in ids]
            P += sum(hits) / a.k
            R += sum(hits) / len(test[s])
            H += any(hits)
            dcg = sum(1 / math.log2(r + 2) for r, h in enumerate(hits) if h)
            idcg = sum(1 / math.log2(r + 2) for r in range(min(len(test[s]), a.k)))
            N += dcg / idcg
        n = max(len(users), 1)
        rows.append({"model": name, f"precision@{a.k}": P / n, f"recall@{a.k}": R / n, "hit_rate": H / n, f"ndcg@{a.k}": N / n})
    out = pd.DataFrame(rows).round(4)
    print(out.to_string(index=False))
    out.to_csv(ROOT / "docs" / "evaluation_results.csv", index=False)


if __name__ == "__main__":
    main()
