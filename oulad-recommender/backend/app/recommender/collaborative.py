"""Item-based collaborative similarity from a sparse student x resource matrix."""
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity


def interaction_matrix(interactions: pd.DataFrame, item_index: dict):
    """interactions: columns student, item, weight (already aggregated or not)."""
    df = interactions[interactions["item"].isin(item_index)]
    df = df.groupby(["student", "item"], as_index=False)["weight"].sum()
    students = {s: i for i, s in enumerate(df["student"].unique())}
    rows = df["student"].map(students).to_numpy()
    cols = df["item"].map(item_index).to_numpy()
    vals = np.log1p(df["weight"].clip(lower=0).to_numpy(dtype=np.float32))
    return csr_matrix((vals, (rows, cols)), shape=(len(students), len(item_index))), students


def item_similarity(matrix: csr_matrix) -> np.ndarray:
    if matrix.shape[0] == 0:
        return np.zeros((matrix.shape[1], matrix.shape[1]), dtype=np.float32)
    sim = cosine_similarity(matrix.T.tocsr(), dense_output=True).astype(np.float32)
    np.fill_diagonal(sim, 0.0)
    return sim


def popularity(matrix: csr_matrix) -> np.ndarray:
    return np.asarray(matrix.sum(axis=0)).ravel().astype(np.float32)
