import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function NetworkPanel({ courses, jobs }) {
  const first = courses?.[0];
  const [course, setCourse] = useState(first ? `${first.code_module}|${first.code_presentation}` : "");
  const [max, setMax] = useState(40);
  const [meta, setMeta] = useState({});
  const [msg, setMsg] = useState("");
  const [view, setView] = useState("interactive");

  useEffect(() => { if (!course && first) setCourse(`${first.code_module}|${first.code_presentation}`); }, [first]); // eslint-disable-line
  const last = (jobs || []).find((j) => j.job_type === "run_network_analysis");
  useEffect(() => { api("/admin/network/meta").then(setMeta).catch(() => {}); }, [last?.status]);

  const run = async () => {
    const [code_module, code_presentation] = course.split("|");
    try { await api("/admin/jobs/network/run", { method: "POST", body: { code_module, code_presentation, max_students: Number(max) } });
      setMsg("Network job queued. The worker needs R installed."); }
    catch (e) { setMsg(e.message); }
  };
  const v = meta.generated_at ? encodeURIComponent(meta.generated_at) : "0";

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Student communities</h2>
        <div className="row-actions">
          <select value={course} onChange={(e) => setCourse(e.target.value)}>
            {(courses || []).map((c) => <option key={c.code_module + c.code_presentation} value={`${c.code_module}|${c.code_presentation}`}>{c.code_module} {c.code_presentation}</option>)}
          </select>
          <input type="number" min="5" max="80" value={max} onChange={(e) => setMax(e.target.value)} title="Students to include" style={{ width: 90 }} />
          <button className="btn primary sm" onClick={run}>Build graph</button>
        </div>
      </div>
      <p className="muted small">Students are linked when they share recommended resources. Groups come from edge-betweenness community detection (R, igraph). Limited to {max} students so it stays readable.</p>
      {msg && <div className="toast">{msg}</div>}
      {last?.status === "failed" && <div className="error">R job failed: {last.error}</div>}
      {meta.generated_at ? (
        <>
          <div className="tabs">
            <button className={`btn sm ${view === "interactive" ? "primary" : "ghost"}`} onClick={() => setView("interactive")}>Interactive</button>
            <button className={`btn sm ${view === "static" ? "primary" : "ghost"}`} onClick={() => setView("static")}>Static plot</button>
            <span className="muted small">{meta.code_module} {meta.code_presentation}: {meta.students} students, {meta.communities} communities, modularity {meta.modularity}</span>
          </div>
          {view === "interactive"
            ? <iframe title="Student community network" className="netframe" src={`/api/v1/static/network/network.html?v=${v}`} />
            : <img className="netimg" alt="Community detection by edge betweenness" src={`/api/v1/static/network/community.png?v=${v}`} />}
          <ul className="rows compact">
            {(meta.groups || []).map((g) => (
              <li key={g.community}><div>Community {g.community}: {g.size} students</div>
                <span className="muted small">top resources {[].concat(g.top_resources).join(", ")}</span></li>))}
          </ul>
        </>
      ) : <p className="muted">No graph yet. Pick a course and press “Build graph” after recommendations exist.</p>}
    </section>
  );
}
