import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from app.processing.bloom_filter import BloomFilter
from app.recommender.artifacts import build_artifact
from app.recommender.hybrid import recommend
from app.services.activity_service import make_event_id


def _art():
    rng = np.random.default_rng(0)
    res = pd.DataFrame({"id_site": range(1, 61), "activity_type": rng.choice(["quiz", "forumng", "oucontent"], 60),
                        "week_from": rng.integers(0, 20, 60), "code_module": "AAA"})
    inter = pd.DataFrame({"student": rng.integers(0, 80, 1500), "item": rng.integers(1, 61, 1500),
                          "weight": rng.integers(1, 9, 1500)})
    return build_artifact("t", "AAA", "2014J", res, inter)


def test_excluded_items_never_recommended():
    out = recommend(_art(), {1: 5, 2: 3}, {1, 2, 3}, 0.5, 10)
    assert out and all(r["resource_id"] not in {1, 2, 3} for r in out)
    assert [r["rank"] for r in out] == list(range(1, len(out) + 1))


def test_cold_start_uses_popularity():
    out = recommend(_art(), {}, set(), 0.5, 5)
    assert len(out) == 5 and out[0]["reason"].startswith("Popular")


def test_scores_are_normalised():
    for r in recommend(_art(), {4: 9}, {4}, 0.5, 10):
        assert 0 <= r["content_score"] <= 1 and 0 <= r["collab_score"] <= 1


def test_event_id_is_idempotent_for_same_client_id():
    assert make_event_id(1, "abc") == make_event_id(1, "abc")
    assert make_event_id(1, "abc") != make_event_id(2, "abc")


def test_bloom_filter_no_false_negatives():
    b = BloomFilter(500)
    for i in range(500):
        b.add(f"k{i}")
    assert all(b.might_contain(f"k{i}") for i in range(500))
