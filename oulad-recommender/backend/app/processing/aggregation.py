"""Local MapReduce-style aggregation: map records to (key, value), then reduce by key.
This runs in one process (no distributed execution)."""
import operator
from collections import defaultdict
from typing import Callable, Iterable


def map_reduce(records: Iterable, mapper: Callable, reducer: Callable = operator.add) -> dict:
    out = {}
    for rec in records:
        for key, value in mapper(rec):
            out[key] = reducer(out[key], value) if key in out else value
    return out


def event_weight_mapper(weights: dict):
    def mapper(ev):
        w = weights.get(ev["event_type"], 0.0)
        if ev.get("resource_id") is not None and w:
            yield (ev["code_module"], ev["code_presentation"], ev["student_id"], ev["resource_id"]), w
    return mapper


def daily_count_mapper(ev):
    yield (ev["occurred_at"].strftime("%Y-%m-%d"), ev["event_type"]), 1


def group_by_first(pairs: dict) -> dict:
    g = defaultdict(list)
    for k, v in pairs.items():
        g[k[0]].append((k[1:], v))
    return g
