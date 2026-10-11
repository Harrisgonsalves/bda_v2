"""Content-based similarity between resources (TF-IDF + cosine)."""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def resource_text(row) -> str:
    """OULAD has no resource titles, so build text from the metadata that exists."""
    wk = pd.to_numeric(row.get("week_from"), errors="coerce")   # real OULAD uses "?" for missing
    week_tok = f"wk{int(wk)//3}" if pd.notna(wk) else "wknone"
    t = str(row["activity_type"])
    return f"{t} {t} type_{t} {row['code_module']} {week_tok}"


def content_similarity(resources: pd.DataFrame) -> np.ndarray:
    texts = [resource_text(r) for r in resources.to_dict("records")]
    tfidf = TfidfVectorizer(token_pattern=r"[A-Za-z0-9_]+")
    m = tfidf.fit_transform(texts)
    sim = cosine_similarity(m).astype(np.float32)
    np.fill_diagonal(sim, 0.0)
    return sim
