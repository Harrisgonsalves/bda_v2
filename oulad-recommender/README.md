# OULAD Hybrid Recommender (Windows)

React + FastAPI + MongoDB + pandas/scikit-learn. Dark-mode UI, student and admin dashboards,
live activity logging, hybrid (content + collaborative) recommendations, and a background worker.

## 1. Install (once)
- Python 3.11 or 3.12, Node.js 20+, MongoDB Community Server (install as a Windows service; default port 27017).
- Download OULAD (https://analyse.kmi.open.ac.uk/open_dataset) and copy the 7 CSVs into `data\raw\`:
  courses, assessments, vle, studentInfo, studentRegistration, studentAssessment, studentVle.

## 2. Backend setup (PowerShell, repo root)
```powershell
copy .env.example .env            # then edit JWT_SECRET
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

## 3. Load data and create logins
```powershell
python scripts\validate_dataset.py --data-dir data\raw
# Full import (~10.6M rows, 10+ min, ~1.5 GB). For a first run use a sample:
python scripts\import_oulad.py --data-dir data\raw --sample-students 8000
python scripts\create_users.py --count 500
```
Admin: `admin@demo.edu` / `admin123`. Students: `student<ID>@demo.edu` / `student123` (the script prints examples).
Re-running the import is safe: small tables are replaced, `studentVle` is skipped unless you pass `--reset-vle`.

## 4. Run (three terminals, venv active in the first two)
```powershell
cd backend; uvicorn app.main:app --reload --port 8000          # API  (docs at http://127.0.0.1:8000/docs)
cd backend; python -m app.worker.runner                         # background worker
cd frontend; npm install; npm run dev                           # UI at http://localhost:5173
```
Then sign in as admin, press **Rebuild recommendations** (worker builds and publishes model v...),
**Rebuild analytics** and **Cluster learners**. Students now get recommendations.

## 4b. Student community graph (R)
Install R 4.x, then in R: `install.packages(c("mongolite","igraph","visNetwork","htmlwidgets","jsonlite"))`.
If `Rscript` is not on PATH, set `RSCRIPT_PATH` in `.env`. In the admin dashboard use **Student communities > Build graph**
(the worker runs `r/community_network.R`). Keep the student count at 80 or below.

## 5. The 100,000-event test
```powershell
python scripts\generate_activity.py --events 100000        # events are labelled source="synthetic"
```
Open the admin dashboard, rebuild recommendations and analytics, and record the timings from the
job table and from `data\synthetic\manifest_seed42.json`.

## 6. Offline evaluation (no database needed)
```powershell
python scripts\evaluate_recommender.py --data-dir data\raw --module AAA --presentation 2014J
```
Trains only on interactions up to a cutoff day and tests on resources first used after it, comparing
popularity, content-only, collaborative-only and hybrid. Results go to `docs\evaluation_results.csv`.

## 7. Tests
`cd backend; pytest tests`

## How the pieces map to the spec
| Spec item | File |
|---|---|
| Collections and indexes | `backend/app/db/indexes.py` |
| Idempotent events, derived student_id | `services/activity_service.py`, `core/security.py` |
| Atomic learner features | `services/feature_service.py` |
| Content, collaborative, hybrid | `recommender/content_based.py`, `collaborative.py`, `hybrid.py` |
| Versioned artifacts, publish-after-success | `recommender/artifacts.py`, `worker/jobs.py` |
| MapReduce-style aggregation, Bloom filter, K-Means | `processing/` |
| Job claiming, retries, stale requeue | `worker/runner.py` |

## Known limits
- OULAD has no resource titles, so content similarity uses activity type, module and week. It is a weak signal;
  expect collaborative scores to carry most of the ranking. Add real titles to `resources.title` to improve it.
- Tokens are stateless JWTs: logout discards the token on the client.
- Dev-only CORS and secrets; change `JWT_SECRET` and demo passwords before sharing.
