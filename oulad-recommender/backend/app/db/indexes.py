from pymongo import ASCENDING as A, DESCENDING as D
from app.db.mongodb import get_db


def create_indexes():
    db = get_db()
    db.users.create_index([("email", A)], unique=True)
    db.users.create_index([("user_id", A)], unique=True)
    db.users.create_index([("student_id", A)])
    db.students.create_index([("id_student", A), ("code_module", A), ("code_presentation", A)])
    db.courses.create_index([("code_module", A), ("code_presentation", A)], unique=True)
    db.resources.create_index([("id_site", A), ("code_module", A), ("code_presentation", A)], unique=True)
    db.resources.create_index([("code_module", A), ("code_presentation", A), ("activity_type", A)])
    db.assessments.create_index([("id_assessment", A)])
    db.student_registrations.create_index([("id_student", A), ("code_module", A), ("code_presentation", A)])
    db.student_assessments.create_index([("id_student", A), ("id_assessment", A)])
    # Not unique: the source can contain several rows for the same student/site/day.
    db.historical_student_vle.create_index(
        [("id_student", A), ("code_module", A), ("code_presentation", A), ("date", A)])
    db.historical_student_vle.create_index([("id_site", A), ("code_module", A), ("code_presentation", A)])
    db.activity_events.create_index([("event_id", A)], unique=True)
    db.activity_events.create_index([("student_id", A), ("occurred_at", D)])
    db.activity_events.create_index([("student_id", A), ("resource_id", A), ("occurred_at", D)])
    db.activity_events.create_index([("occurred_at", D)])
    db.learner_features.create_index(
        [("student_id", A), ("code_module", A), ("code_presentation", A)], unique=True)
    db.recommendations.create_index(
        [("student_id", A), ("code_module", A), ("code_presentation", A), ("resource_id", A), ("model_version", A)],
        unique=True)
    db.recommendations.create_index(
        [("student_id", A), ("code_module", A), ("code_presentation", A), ("rank", A)])
    db.job_runs.create_index([("status", A), ("started_at", D)])
    db.job_runs.create_index([("created_at", D)])
    db.analytics_summaries.create_index([("key", A)], unique=True)
    db.model_metadata.create_index([("version", A)], unique=True)
