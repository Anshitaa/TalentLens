import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import { getModelRuns, getDriftReports, getOverrides } from "../api";
import { Card, KpiCard, Spinner, ErrorMsg, PAGE_TITLE } from "../components/Card";

const TT_STYLE = { background:"#18181b", border:"1px solid #27272a", borderRadius:6, fontSize:12, color:"#fafafa" };

export default function ModelGovernance() {
  const [runs,      setRuns]      = useState([]);
  const [drift,     setDrift]     = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [err,       setErr]       = useState(null);
  const [loading,   setLoading]   = useState(true);

  useEffect(() => {
    Promise.all([getModelRuns(), getDriftReports(), getOverrides()])
      .then(([r, d, o]) => { setRuns(r); setDrift(d); setOverrides(o); })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (err)     return <ErrorMsg msg={err} />;

  const driftChart = drift.slice().reverse().map(d => ({
    date: new Date(d.run_date).toLocaleDateString("en-US", { month:"short", day:"numeric" }),
    psi:  Number(d.psi_score),
  }));

  const latestPsi = drift[0]?.psi_score ? Number(drift[0].psi_score) : null;
  const psiColor  = latestPsi == null ? "#6366f1" : latestPsi > 0.2 ? "#ef4444" : "#22c55e";

  return (
    <div>
      <h1 style={{ ...PAGE_TITLE, marginBottom:24 }}>Model Governance</h1>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14, marginBottom:20 }}>
        <KpiCard label="MLflow Runs"    value={runs.length}  color="#6366f1" />
        <KpiCard label="Latest PSI Score"
          value={latestPsi != null ? latestPsi.toFixed(4) : "—"}
          color={psiColor}
          sub={drift[0]?.retrain_triggered ? "Retrain triggered" : drift.length ? "Stable" : undefined} />
        <KpiCard label="HITL Overrides" value={overrides.length} color="#f59e0b" />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
        <Card title="PSI Drift Over Time">
          {driftChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={210}>
              <LineChart data={driftChart} margin={{ top:4, right:8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="date" tick={{ fill:"#71717a", fontSize:10 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0,1]} tick={{ fill:"#71717a", fontSize:10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TT_STYLE} />
                <ReferenceLine y={0.2} stroke="#f59e0b" strokeDasharray="4 2" label={{ value:"Threshold", fill:"#f59e0b", fontSize:10 }} />
                <Line type="monotone" dataKey="psi" stroke="#6366f1" strokeWidth={2} dot={{ r:3, fill:"#6366f1" }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color:"#52525b", textAlign:"center", padding:50, fontSize:13 }}>No drift reports yet</div>
          )}
        </Card>

        <Card title="MLflow Model Runs">
          {runs.length > 0 ? (
            <div style={{ overflow:"auto", maxHeight:210 }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                <thead>
                  <tr style={{ borderBottom:"1px solid #27272a" }}>
                    {["Experiment","AUC","PR-AUC","Status"].map(h => (
                      <th key={h} style={{ padding:"6px 10px", textAlign:"left", fontWeight:500,
                        color:"#52525b", fontSize:11, textTransform:"uppercase", letterSpacing:"0.5px" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r, i) => (
                    <tr key={i} style={{ borderBottom:"1px solid #1f1f23" }}>
                      <td style={{ padding:"7px 10px", color:"#a1a1aa", fontSize:11 }}>{r.experiment_name || "—"}</td>
                      <td style={{ padding:"7px 10px", color:"#fafafa" }}>{r.metrics?.val_roc_auc?.toFixed(4) ?? "—"}</td>
                      <td style={{ padding:"7px 10px", color:"#fafafa" }}>{r.metrics?.val_pr_auc?.toFixed(4) ?? "—"}</td>
                      <td style={{ padding:"7px 10px" }}>
                        <span style={{ fontSize:11, fontWeight:500,
                          color: r.status === "FINISHED" ? "#22c55e" : "#f59e0b" }}>
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ color:"#52525b", textAlign:"center", padding:50, fontSize:13 }}>No MLflow runs found</div>
          )}
        </Card>
      </div>

      <Card title="HITL Override Log">
        {overrides.length > 0 ? (
          <div style={{ overflow:"auto", maxHeight:300 }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead>
                <tr style={{ borderBottom:"1px solid #27272a" }}>
                  {["Employee","Reviewer","Orig. Risk","Decision","Reason","Time"].map(h => (
                    <th key={h} style={{ padding:"7px 12px", textAlign:"left", fontWeight:500,
                      color:"#52525b", fontSize:11, textTransform:"uppercase", letterSpacing:"0.5px" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {overrides.slice(0, 30).map((o, i) => (
                  <tr key={i} style={{ borderBottom:"1px solid #1f1f23" }}>
                    <td style={{ padding:"8px 12px", fontFamily:"ui-monospace,monospace", fontSize:10, color:"#52525b" }}>
                      {String(o.employee_id).slice(0,8)}…
                    </td>
                    <td style={{ padding:"8px 12px", color:"#a1a1aa" }}>{o.reviewer_id}</td>
                    <td style={{ padding:"8px 12px", color:"#fafafa" }}>{Number(o.original_risk_index).toFixed(1)}</td>
                    <td style={{ padding:"8px 12px" }}>
                      <span style={{ fontSize:11, fontWeight:600,
                        color: o.override_label === 0 ? "#22c55e" : "#ef4444" }}>
                        {o.override_label === 0 ? "Not at risk" : "At risk"}
                      </span>
                    </td>
                    <td style={{ padding:"8px 12px", color:"#71717a", maxWidth:200,
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      {o.reason}
                    </td>
                    <td style={{ padding:"8px 12px", color:"#52525b", fontSize:10 }}>
                      {o.override_at ? new Date(o.override_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color:"#52525b", textAlign:"center", padding:50, fontSize:13 }}>No overrides recorded</div>
        )}
      </Card>
    </div>
  );
}
