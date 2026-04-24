import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { getHiringFunnel, getHiringSummary } from "../api";
import { Card, KpiCard, Spinner, ErrorMsg } from "../components/Card";

export default function HiringFunnel() {
  const [funnel,  setFunnel]  = useState([]);
  const [summary, setSummary] = useState(null);
  const [err,     setErr]     = useState(null);

  useEffect(() => {
    Promise.all([getHiringFunnel(), getHiringSummary()])
      .then(([f,s]) => { setFunnel(f); setSummary(s); })
      .catch(e => setErr(e.message));
  }, []);

  if (err)     return <ErrorMsg msg={err} />;
  if (!summary) return <Spinner />;

  return (
    <div>
      <h1 style={{ margin:"0 0 20px", fontSize:22, color:"#e2e8f0" }}>Hiring Funnel Analytics</h1>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16, marginBottom:24 }}>
        <KpiCard label="Total Candidates" value={summary.total_candidates?.toLocaleString()} color="#7c3aed" />
        <KpiCard label="Hire Rate" value={`${(Number(summary.hire_rate||0)*100).toFixed(1)}%`} color="#22c55e" />
        <KpiCard label="Avg Days to Close" value={Number(summary.avg_days_to_close||0).toFixed(1)} color="#f59e0b" />
        <KpiCard label="Departments" value={funnel.length} color="#94a3b8" />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
        <Card title="Days to Close by Department">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={funnel} margin={{ left:10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
              <XAxis dataKey="department" tick={{ fill:"#94a3b8", fontSize:10 }} angle={-30} textAnchor="end" height={50} />
              <YAxis tick={{ fill:"#94a3b8", fontSize:10 }} />
              <Tooltip contentStyle={{ background:"#1a1f2e", border:"1px solid #2d3748" }} />
              <Legend wrapperStyle={{ color:"#94a3b8", fontSize:11 }} />
              <Bar dataKey="avg_days_to_screen"    name="To Screen"    fill="#7c3aed" stackId="a" />
              <Bar dataKey="avg_days_to_interview" name="To Interview"  fill="#a78bfa" stackId="a" />
              <Bar dataKey="avg_days_to_offer"     name="To Offer"     fill="#c4b5fd" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Hire Rate by Department">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={funnel} layout="vertical" margin={{ left:60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
              <XAxis type="number" domain={[0,1]} tickFormatter={v=>`${(v*100).toFixed(0)}%`} tick={{ fill:"#94a3b8", fontSize:10 }} />
              <YAxis type="category" dataKey="department" width={60} tick={{ fill:"#94a3b8", fontSize:10 }} />
              <Tooltip contentStyle={{ background:"#1a1f2e", border:"1px solid #2d3748" }}
                formatter={v=>`${(v*100).toFixed(1)}%`} />
              <Bar dataKey="hire_rate" fill="#22c55e" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
