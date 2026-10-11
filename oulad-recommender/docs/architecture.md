# Architecture
Browser (React) -> FastAPI (/api/v1) -> MongoDB <- Worker process (job_runs queue).
Request path: validate event -> insert into activity_events (unique event_id) -> $inc learner_features -> re-rank with
cached artifacts -> upsert recommendations. The worker rebuilds artifacts per course presentation, bulk-refreshes
recommendations under the new version, then flips model_metadata.is_active.
