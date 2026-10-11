import { useState } from "react";
import { api, auth } from "./api/client";
import Login from "./pages/Login";
import StudentDashboard from "./pages/StudentDashboard";
import AdminDashboard from "./pages/AdminDashboard";

export default function App() {
  const [user, setUser] = useState(auth.user);
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ }
    auth.clear(); setUser(null);
  };
  if (!user) return <Login onLogin={setUser} />;
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Learning Resource Recommender</div>
        <div className="who">
          <span>{user.email}</span>
          <span className="pill">{user.role}</span>
          <button className="btn ghost" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main className="page">
        {user.role === "admin" ? <AdminDashboard /> : <StudentDashboard user={user} />}
      </main>
    </div>
  );
}
