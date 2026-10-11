import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

LABELS = ["Low engagement", "Light engagement", "Steady engagement", "High engagement",
          "Very high engagement", "Intensive"]


def cluster_learners(df: pd.DataFrame, k: int = 4, seed: int = 42):
    """df columns: total_clicks, active_rows, final_result (optional). Features are standardised first."""
    feats = pd.DataFrame({
        "log_clicks": np.log1p(df["total_clicks"]),
        "log_rows": np.log1p(df["active_rows"]),
        "clicks_per_row": df["total_clicks"] / df["active_rows"].clip(lower=1)})
    x = StandardScaler().fit_transform(feats)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(x)
    df = df.assign(cluster=km.labels_)
    order = df.groupby("cluster")["total_clicks"].mean().sort_values().index.tolist()
    names = {c: LABELS[i] for i, c in enumerate(order)}
    out = []
    for c in order:
        g = df[df["cluster"] == c]
        mix = (g["final_result"].value_counts(normalize=True).round(3).to_dict()
               if "final_result" in g else {})
        out.append({"cluster": int(c), "label": names[c], "size": int(len(g)),
                    "avg_clicks": round(float(g["total_clicks"].mean()), 1),
                    "avg_active_rows": round(float(g["active_rows"].mean()), 1), "final_result_mix": mix})
    return out, df
