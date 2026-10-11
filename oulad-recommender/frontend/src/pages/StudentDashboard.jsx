import { useCallback, useEffect, useState } from "react";
import { api, newEventId } from "../api/client";
import RecommendationCard from "../components/RecommendationCard";
import ResourceBrowser from "../components/ResourceBrowser";
import Stat from "../components/Stat";

const label = { resource_opened: "Opened", resource_completed: "Completed", search_performed: "Searched",
                feedback_useful: "Marked useful", feedback_not_useful: "Marked not for me" };

export default function StudentDashboard() {
  const [courses, setCourses] = useState([]);
  const [course, setCourse] = useState(null);
  const [recs, setRecs] = useState({ items: [], ready: true });
  const [progress, setProgress] = useState(null);
  const [activity, setActivity] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api("/student/courses").then((c) => {
      setCourses(c);
      if (c.length) setCourse({ m: c[0].code_module, p: c[0].code_presentation });
    });
  }, []);

  const params = course && { code_module: course.m, code_presentation: course.p };
  const refresh = useCallback(async () => {
    if (!course) return;
    const [r, p, a] = await Promise.all([
      api("/student/recommendations", { params }), api("/student/progress", { params }),
      api("/student/activity", { params: { ...params, limit: 8 } })]);
    setRecs(r); setProgress(p); setActivity(a);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [course]);
  useEffect(() => { refresh().catch((e) => setMsg(e.message)); }, [refresh]);

  const send = async (path, body, okText) => {
    setBusy(true); setMsg("");
    try {
      const r = await api(path, { method: "POST", body: { ...body, code_module: course.m, code_presentation: course.p, client_event_id: newEventId() } });
      if (r.recommendations) setRecs((s) => ({ ...s, items: r.recommendations }));
      setMsg(r.duplicate ? "That action was already recorded." : okText);
      const [p, a] = await Promise.all([api("/student/progress", { params }), api("/student/activity", { params: { ...params, limit: 8 } })]);
      setProgress(p); setActivity(a);
    } catch (e) { setMsg(e.message); } finally { setBusy(false); }
  };
  const open = (r) => send("/student/events", { event_type: "resource_opened", resource_id: r.resource_id }, "Opened. Recommendations updated.");
  const complete = (r) => send("/student/events", { event_type: "resource_completed", resource_id: r.resource_id }, "Marked complete. Recommendations updated.");
  const feedback = (r, useful) => send("/student/recommendations/feedback", { resource_id: r.resource_id, useful }, "Thanks, your feedback was saved.");

  if (!course) return <div className="muted">Loading your courses…</div>;
  const pct = progress && progress.resources_total ? Math.round((progress.resources_touched / progress.resources_total) * 100) : 0;

  return (
    <div className="grid">
      <div className="col-main">
        <div className="toolbar">
          <div>
            <h1>Recommended for you</h1>
            <p className="muted">Ranked from what you and similar learners used. Bars show how much comes from similar content (blue) versus similar learners (green).</p>
          </div>
          <select value={`${course.m}|${course.p}`} onChange={(e) => { const [m, p] = e.target.value.split("|"); setCourse({ m, p }); }}>
            {courses.map((c) => <option key={c.code_module + c.code_presentation} value={`${c.code_module}|${c.code_presentation}`}>{c.code_module} {c.code_presentation}</option>)}
          </select>
        </div>
        {msg && <div className="toast" role="status">{msg}</div>}
        {!recs.ready && <div className="panel empty">Recommendations are not ready yet. An administrator needs to run the recommendation rebuild first.</div>}
        {recs.ready && !recs.items.length && <div className="panel empty">You have seen every resource in this course. Nice work.</div>}
        <div className="rec-list">
          {recs.items.map((r) => <RecommendationCard key={r.resource_id} rec={r} busy={busy} onOpen={open} onComplete={complete} onFeedback={feedback} />)}
        </div>
        <ResourceBrowser course={course} onOpen={open} />
      </div>
      <aside className="col-side">
        <section className="panel">
          <h2>Your progress</h2>
          <div className="meter"><span style={{ width: `${pct}%` }} /></div>
          <p className="muted small">{progress ? `${progress.resources_touched} of ${progress.resources_total} resources used (${pct}%)` : ""}</p>
          <div className="stats">
            <Stat label="Completed" value={progress?.resources_completed} />
            <Stat label="Past clicks" value={progress?.historical_clicks?.toLocaleString()} />
            <Stat label="New actions" value={progress?.app_events} />
          </div>
        </section>
        <section className="panel">
          <h2>Recent activity</h2>
          <ul className="rows compact">
            {activity.map((a) => (
              <li key={a.event_id}>
                <div>{label[a.event_type] || a.event_type}{a.resource_id ? ` · ${a.resource_id}` : ""}</div>
                <span className="muted small">{new Date(a.occurred_at).toLocaleString()}</span>
              </li>
            ))}
            {!activity.length && <li className="muted">Nothing yet. Open a resource to get started.</li>}
          </ul>
        </section>
      </aside>
    </div>
  );
}
