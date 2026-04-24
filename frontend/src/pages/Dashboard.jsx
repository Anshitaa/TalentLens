import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";
import { getRiskSummary, getRiskTop, getRiskByDept } from "../api";
import { Card, KpiCard, BandBadge, Spinner, ErrorMsg, BAND_COLOR, PAGE_TITLE } from "../components/Card";

const TT_STYLE = { background:"#18181b", border:"1px solid #27272a", borderRadius:6, fontSize:12, color:"#fafafa" };

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [top,     setTop]     = useState([]);
  const [byDept,  setByDept]  = useState([]);
  const [err,     setErr]     = useState(null);
  const [live,    setLive]    = useState(null);

  useEffect(() => {
    Promise.all([getRiskSummary(), getRiskTop(), getRiskByDept()])
      .then(([s, t, d]) => { setSummary(s); setTop(t); setByDept(d); })
      .catch(e => setErr(e.message));

    const socket = new WebSocket("ws://127.0.0.1:8000/ws/dashboard");
    socket.onmessage = e => { try { setLive(JSON.parse(e.data)); } catch {} };
    socket.onerror = () => {};
    return () => socket.close();
  }, []);

  if (err)      return <ErrorMsg msg={err} />;
  if (!summary) return <Spinner />;

  const pieData = ["Low","Medium","High","Critical"].map(b => ({
    name: b, value: summary.band_counts?.[b] ?? 0,
  }));

  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:24 }}>
        <h1 style={PAGE_TITLE}>Workforce Risk Dashboard</h1>
        {live && (
          <span style={{ fontSize:11, color:"#22c55e", display:"flex", alignItems:"center", gap:5, fontWeight:500 }}>
            <span style={{ width:6, height:6, borderRadius:"50%", background:"#22c55e", display:"inline-block" }} />
            Live
          </span>
        )}
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14, marginBottom:20 }}>
        <KpiCard label="Total Scored"   value={summary.total?.toLocaleString()}                color="#6366f1" />
        <KpiCard label="Avg Risk Index" value={summary.avg_risk_index?.toFixed(1)}              color="#f59e0b" />
        <KpiCard label="High / Critical" value={`${summary.pct_high_critical?.toFixed(1)}%`}   color="#f97316" />
        <KpiCard label="Critical"        value={summary.band_counts?.Critical ?? 0}             color="#ef4444" />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
        <Card title="Risk Band Distribution">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                outerRadius={80} innerRadius={40}
                label={({ name, value }) => value > 0 ? `${name}: ${value.toLocaleString()}` : ""}>
                {pieData.map(e => <Cell key={e.name} fill={BAND_COLOR[e.name]} />)}
              </Pie>
              <Tooltip contentStyle={TT_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Avg Risk Index by Department">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byDept} layout="vertical" margin={{ left:60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis type="number" domain={[0,100]} tick={{ fill:"#71717a", fontSize:11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="department" tick={{ fill:"#a1a1aa", fontSize:11 }} width={60} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TT_STYLE} cursor={{ fill:"#27272a" }} />
              <Bar dataKey="avg_risk_index" fill="#6366f1" radius={[0,4,4,0]} maxBarSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Top At-Risk Employees">
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead>
            <tr style={{ borderBottom:"1px solid #27272a" }}>
              {["Employee ID","Department","Level","Risk Index","Band","Flight Risk"].map(h => (
                <th key={h} style={{ padding:"8px 12px", textAlign:"left", fontWeight:500,
                  color:"#52525b", fontSize:11, textTransform:"uppercase", letterSpacing:"0.5px" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {top.slice(0,15).map((r, i) => (
              <tr key={i} style={{ borderBottom:"1px solid #1f1f23" }}
                onMouseEnter={e => e.currentTarget.style.background="#1c1c1f"}
                onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                <td style={{ padding:"9px 12px", fontFamily:"ui-monospace,monospace", fontSize:11, color:"#52525b" }}>
                  {r.employee_id?.slice(0,8)}…
                </td>
                <td style={{ padding:"9px 12px", color:"#a1a1aa" }}>{r.department}</td>
                <td style={{ padding:"9px 12px", color:"#71717a" }}>{r.job_level}</td>
                <td style={{ padding:"9px 12px", fontWeight:600,
                  color: (r.latest_risk_index ?? 0) > 40 ? "#f97316" : "#f59e0b" }}>
                  {r.latest_risk_index != null ? Number(r.latest_risk_index).toFixed(1) : "—"}
                </td>
                <td style={{ padding:"9px 12px" }}><BandBadge band={r.latest_risk_band} /></td>
                <td style={{ padding:"9px 12px", color:"#71717a" }}>
                  {r.flight_risk_prob != null ? `${(Number(r.flight_risk_prob)*100).toFixed(1)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
