"""Hybrid scoring  S(u,r) = alpha*C(u,r) + (1-alpha)*CF(u,r)."""
import numpy as np
from app.recommender.artifacts import Artifact


def _norm(x: np.ndarray) -> np.ndarray:
    lo, hi = float(x.min()), float(x.max())
    return np.zeros_like(x) if hi - lo < 1e-9 else (x - lo) / (hi - lo)


def profile_vector(a: Artifact, weights: dict) -> np.ndarray:
    w = np.zeros(len(a.item_ids), dtype=np.float32)
    for rid, val in weights.items():
        k = a.item_index.get(int(rid))
        if k is not None and val > 0:
            w[k] = np.log1p(val)
    return w


def score(a: Artifact, w: np.ndarray, alpha: float):
    c = a.content_sim @ w
    cf = a.cf_sim @ w
    return _norm(c), _norm(cf)


def recommend(a: Artifact, weights: dict, exclude: set, alpha: float = 0.5, top_k: int = 20,
              mode: str = "hybrid") -> list:
    """mode: hybrid | content | collaborative (used by the evaluation script)."""
    w = profile_vector(a, weights)
    pop = _norm(a.popularity)
    cold = w.sum() == 0
    if cold:
        final, c, cf = pop, np.zeros_like(pop), np.zeros_like(pop)
    else:
        c, cf = score(a, w, alpha)
        if mode == "content":
            final = c
        elif mode == "collaborative":
            final = cf
        else:
            final = alpha * c + (1 - alpha) * cf
        final = final + 1e-4 * pop           # popularity only breaks ties
    mask = np.array([i in exclude for i in a.item_ids])
    final = np.where(mask, -1.0, final)
    order = np.argsort(-final)[:top_k]
    out = []
    for rank, k in enumerate(order, start=1):
        if final[k] < 0:
            break
        out.append({
            "rank": rank, "resource_id": a.item_ids[k], "activity_type": a.item_type[k],
            "week_from": a.item_week[k], "score": round(float(final[k]), 5),
            "content_score": round(float(c[k]), 5), "collab_score": round(float(cf[k]), 5),
            "reason": _reason(a, w, k, c[k], cf[k], alpha, cold)})
    return out


def _reason(a, w, k, c, cf, alpha, cold):
    if cold:
        return "Popular with learners in this course"
    if (1 - alpha) * cf >= alpha * c:
        return "Popular among learners with similar activity"
    j = int(np.argmax(a.content_sim[k] * w))
    return f"Similar to {a.item_type[j]} resources you recently used"
