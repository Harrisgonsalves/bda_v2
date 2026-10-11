import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import Stat from "../components/Stat";
import NetworkPanel from "../components/NetworkPanel";

const C = { opened: "#8EA2FF", completed: "#5EE0B0", search: "#F2B65E", up: "#B79CFF", down: "#FF7A8A" };
const axis = { stroke: "#8D97B5", fontSize: 12 };
const tip = { contentStyle: { background: "#1C2438", border: "1px solid #2A3350", borderRadius: 8, color: "#E6EAF5" } };
const fmt = (d) => (d ? new Date(d).toLocaleString() : "–");

export default function AdminDashboard() {
  const overview = useAsync(() => api("/admin/overview"));
  const trend = useAsync(() => api("/admin/analytics/activity", { params: { days: 30 } }));
  const popular = useAsync(() => api("/admin/resources/popular", { params: { limit: 10 } }));
  const recStats = useAsync(() => api("/admin/analytics/recommendations"));
  const model = useAsync(() => api("/admin/models/current"));
  const clusters = useAsync(() => api("/admin/analytics/clusters"));
  const courses = useAsync(() => api("/admin/courses"));
  const jobs = useAsync(() => api("/admin/jobs"));
  const [q, setQ] = useState("");
  const students = useAsync(() => api("/admin/students", { params: { q, limit: 10 } }), [q]);
  const [msg, setMsg] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {          // poll job status while anything is queued or running
    const active = (jobs.data || []).some((j) => ["pending", "running"].includes(j.status));
    const t = setInterval(() => { jobs.reload(); if (active) { model.reload(); overview.reload(); } }, active ? 3000 : 10000);
    return () => clearInterval(t);
  }, [jobs.data]); // eslint-disable-line

  const start = async (path) => {
    setMsg("");
    try { await api(path, { method: "POST" }); setMsg("Job queued. Make sure the worker is running."); jobs.reload(); }
    catch (e) { setMsg(e.message); }
  };
  const inspect = async (id) => setDetail(await api(`/admin/students/${id}`));

  const o = overview.data || {};
  const r = recStats.data || {};
  const hist = (popular.data?.historical || []).slice(0, 10).map((x) => ({ name: `${x.code_module} ${x.resource_id}`, clicks: x.clicks }));
  const live = (popular.data?.live || []).map((x) => ({ name: `${x.code_module} ${x.resource_id}`, events: x.events }));

  return (
    <div className="admin">
      <h1>Platform overview</h1>
      <div className="stats wide">
        <Stat label="Student accounts" value={o.accounts?.toLocaleString()} hint={`${o.students?.toLocaleString() ?? "–"} learner records`} />
        <Stat label="Resources" value={o.resources?.toLocaleString()} />
        <Stat label="Historical OULAD rows" value={o.historical_rows?.toLocaleString()} />
        <Stat label="New events" value={o.app_events?.toLocaleString()} hint={`${o.synthetic_events?.toLocaleString() ?? 0} synthetic`} />
        <Stat label="Stored recommendations" value={o.recommendations?.toLocaleString()} />
        <Stat label="Useful rate" value={r.useful_rate != null ? `${Math.round(r.useful_rate * 100)}%` : "–"} hint={`${o.feedback_total ?? 0} feedback events`} />
      </div>

      <div className="two">
        <section className="panel">
          <h2>Activity, last 30 days</h2>
          <div className="chart">
            <ResponsiveContainer>
              <BarChart data={trend.data || []}>
                <CartesianGrid stroke="#2A3350" vertical={false} />
                <XAxis dataKey="day" {...axis} tickFormatter={(d) => d.slice(5)} /><YAxis {...axis} />
                <Tooltip {...tip} /><Legend />
                <Bar dataKey="resource_opened" name="Opened" stackId="a" fill={C.opened} />
                <Bar dataKey="resource_completed" name="Completed" stackId="a" fill={C.completed} />
                <Bar dataKey="search_performed" name="Searched" stackId="a" fill={C.search} />
                <Bar dataKey="feedback_useful" name="Useful" stackId="a" fill={C.up} />
                <Bar dataKey="feedback_not_useful" name="Not useful" stackId="a" fill={C.down} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <h2>Most used resources</h2>
          <p className="muted small">Historical clicks come from the OULAD import; run the analytics rebuild to fill this chart.</p>
          <div className="chart">
            <ResponsiveContainer>
              <BarChart data={hist.length ? hist : live} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid stroke="#2A3350" horizontal={false} />
                <XAxis type="number" {...axis} /><YAxis type="category" dataKey="name" width={90} {...axis} />
                <Tooltip {...tip} />
                <Bar dataKey={hist.length ? "clicks" : "events"} fill={C.opened} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Background jobs</h2>
          <div className="row-actions">
            <button className="btn primary sm" onClick={() => start("/admin/jobs/recommendations/rebuild")}>Rebuild recommendations</button>
            <button className="btn sm" onClick={() => start("/admin/jobs/analytics/rebuild")}>Rebuild analytics</button>
            <button className="btn sm" onClick={() => start("/admin/jobs/clustering/run")}>Cluster learners</button>
          </div>
        </div>
        {msg && <div className="toast">{msg}</div>}
        <div className="table-wrap"><table>
          <thead><tr><th>Job</th><th>Status</th><th>Created</th><th>Finished</th><th>Processed</th><th>Model</th><th>Error</th></tr></thead>
          <tbody>
            {(jobs.data || []).map((j) => (
              <tr key={j.job_id}>
                <td>{j.job_type.replaceAll("_", " ")}</td>
                <td><span className={`badge ${j.status}`}>{j.status}</span></td>
                <td>{fmt(j.created_at)}</td><td>{fmt(j.finished_at)}</td>
                <td>{j.processed}</td><td>{j.model_version || "–"}</td><td className="muted">{j.error || ""}</td>
              </tr>
            ))}
            {!jobs.data?.length && <tr><td colSpan="7" className="muted">No jobs yet. Start with “Rebuild recommendations”.</td></tr>}
          </tbody>
        </table></div>
      </section>

      <div className="two">
        <section className="panel">
          <h2>Active model</h2>
          {model.data?.version ? (
            <dl className="kv">
              <dt>Version</dt><dd>{model.data.version}</dd>
              <dt>Trained</dt><dd>{fmt(model.data.trained_at)}</dd>
              <dt>Training time</dt><dd>{model.data.training_seconds}s</dd>
              <dt>Courses built</dt><dd>{model.data.courses_built}</dd>
              <dt>Hybrid weight α</dt><dd>{model.data.alpha}</dd>
              <dt>Students refreshed</dt><dd>{model.data.students_refreshed}</dd>
            </dl>
          ) : <p className="muted">{model.data?.message || "Loading…"}</p>}
        </section>
        <section className="panel">
          <h2>Learner clusters</h2>
          {clusters.data?.clusters ? (
            <div className="table-wrap"><table>
              <thead><tr><th>Group</th><th>Learners</th><th>Avg clicks</th><th>Pass or distinction</th></tr></thead>
              <tbody>{clusters.data.clusters.map((c) => {
                const mix = c.final_result_mix || {};
                return <tr key={c.cluster}><td>{c.label}</td><td>{c.size.toLocaleString()}</td><td>{c.avg_clicks}</td>
                  <td>{Math.round(((mix.Pass || 0) + (mix.Distinction || 0)) * 100)}%</td></tr>;
              })}</tbody>
            </table></div>
          ) : <p className="muted">Run “Cluster learners” to group learners by activity.</p>}
        </section>
      </div>

      <NetworkPanel courses={courses.data} jobs={jobs.data} />

      <section className="panel">
        <h2>Courses</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>Module</th><th>Presentation</th><th>Students</th><th>Resources</th><th>Historical clicks</th><th>New events</th></tr></thead>
          <tbody>{(courses.data || []).map((c) => (
            <tr key={c.code_module + c.code_presentation}>
              <td>{c.code_module}</td><td>{c.code_presentation}</td><td>{c.students ?? "–"}</td>
              <td>{c.resources ?? "–"}</td><td>{c.historical_clicks?.toLocaleString() ?? "–"}</td><td>{c.app_events ?? "–"}</td>
            </tr>))}</tbody>
        </table></div>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Students</h2>
          <input placeholder="Search by email or student ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="table-wrap"><table>
          <thead><tr><th>Student ID</th><th>Email</th><th></th></tr></thead>
          <tbody>{(students.data?.items || []).map((s) => (
            <tr key={s.user_id}><td>{s.student_id}</td><td>{s.email}</td>
              <td><button className="btn ghost sm" onClick={() => inspect(s.student_id)}>Inspect</button></td></tr>))}</tbody>
        </table></div>
        {detail && (
          <div className="detail">
            <div className="panel-head"><h3>Student {detail.student_id}</h3><button className="btn ghost sm" onClick={() => setDetail(null)}>Close</button></div>
            <p className="muted small">Enrolments: {detail.enrolments.map((e) => `${e.code_module} ${e.code_presentation} (${e.final_result})`).join(", ")}</p>
            <ul className="rows compact">{detail.recent_events.slice(0, 10).map((e) => (
              <li key={e.event_id}><div>{e.event_type}{e.resource_id ? ` · ${e.resource_id}` : ""} <span className={`badge ${e.source}`}>{e.source}</span></div>
                <span className="muted small">{fmt(e.occurred_at)}</span></li>))}
              {!detail.recent_events.length && <li className="muted">No application events yet.</li>}</ul>
          </div>
        )}
      </section>
    </div>
  );
}
