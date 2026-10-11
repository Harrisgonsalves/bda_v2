import { useEffect, useState } from "react";
import { api, newEventId } from "../api/client";

export default function ResourceBrowser({ course, onOpen }) {
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState({ items: [], total: 0, activity_types: [] });
  const limit = 12;

  useEffect(() => { setSkip(0); }, [course.m, course.p, q, type]);
  useEffect(() => {
    const t = setTimeout(() => {
      api("/student/resources", { params: { code_module: course.m, code_presentation: course.p, q, activity_type: type, skip, limit } })
        .then(setData).catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [course.m, course.p, q, type, skip]);

  const search = () => q && api("/student/events", { method: "POST", body: {
    event_type: "search_performed", code_module: course.m, code_presentation: course.p, query: q, client_event_id: newEventId() } }).catch(() => {});

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Browse resources</h2>
        <span className="muted small">{data.total} in this course</span>
      </div>
      <div className="filters">
        <input placeholder="Search by name or type" value={q} onChange={(e) => setQ(e.target.value)} onBlur={search}
               onKeyDown={(e) => e.key === "Enter" && search()} />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {data.activity_types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <ul className="rows">
        {data.items.map((r) => (
          <li key={r.id_site}>
            <div><strong>{r.title}</strong><div className="muted small">{r.activity_type}{r.week_from != null ? `, week ${r.week_from}` : ""}</div></div>
            <button className="btn sm" onClick={() => onOpen({ resource_id: r.id_site })}>Open</button>
          </li>
        ))}
        {!data.items.length && <li className="muted">No resources match. Try a different word or clear the type filter.</li>}
      </ul>
      <div className="pager">
        <button className="btn ghost sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - limit))}>Previous</button>
        <span className="muted small">{data.total ? `${skip + 1}–${Math.min(skip + limit, data.total)}` : "0"}</span>
        <button className="btn ghost sm" disabled={skip + limit >= data.total} onClick={() => setSkip(skip + limit)}>Next</button>
      </div>
    </section>
  );
}
