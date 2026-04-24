import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getRiskScores } from "../api";
import { Card, BandBadge, Spinner, ErrorMsg, BAND_COLOR } from "../components/Card";

const DEPTS = ["","Engineering","Sales","Finance","HR","Marketing","Operations","Legal","Product"];
const BANDS = ["","Low","Medium","High","Critical"];

export default function RiskExplorer() {
  const [rows,   setRows]   = useState([]);
  const [band,   setBand]   = useState("");
  const [dept,   setDept]   = useState("");
  const [search, setSearch] = useState("");
  const [err,    setErr]    = useState(null);
  const [loading,setLoading]= useState(true);

  useEffect(() => {
    setLoading(true);
    const params = { limit: 200 };
    if (band) params.band = band;
    if (dept) params.dept = dept;
    getRiskScores(params)
      .then(d => { setRows(d); setLoading(false); })
      .catch(e => { setErr(e.message); setLoading(false); });
  }, [band, dept]);

  const filtered = rows.filter(r =>
    !search || r.employee_id?.toLowerCase().includes(search.toLowerCase()) ||
    r.department?.toLowerCase().includes(search.toLowerCase())
  );

  const shap = filtered.slice(0,20).map(r => ({
    name: r.shap_top_feature_1 || "—",
    value: Math.abs(Number(r.shap_value_1) || 0),
  })).reduce((acc, cur) => {
    const ex = acc.find(a => a.name === cur.name);
    ex ? ex.value += cur.value : acc.push({ ...cur });
    return acc;
  }, []).sort((a,b) => b.value - a.value).slice(0,8);

  if (err) return <ErrorMsg msg={err} />;

  const inp = { background:"#0f1117", border:"1px solid #2d3748", color:"#e2e8f0", borderRadius:6, padding:"6px 12px", fontSize:13 };

  return (
    <div>
      <h1 style={{ margin:"0 0 20px", fontSize:22, color:"#e2e8f0" }}>Risk Explorer</h1>

      {/* Filters */}
      <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
        <input placeholder="Search employee / department…" value={search}
          onChange={e=>setSearch(e.target.value)} style={{ ...inp, width:260 }} />
        <select value={band} onChange={e=>setBand(e.target.value)} style={inp}>
          {BANDS.map(b=><option key={b} value={b}>{b||"All Bands"}</option>)}
        </select>
        <select value={dept} onChange={e=>setDept(e.target.value)} style={inp}>
          {DEPTS.map(d=><option key={d} value={d}>{d||"All Departments"}</option>)}
        </select>
        <span style={{ color:"#64748b", fontSize:13, alignSelf:"center" }}>{filtered.length} results</span>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 320px", gap:16 }}>
        {/* Table */}
        <Card title="Employee Risk Scores">
          {loading ? <Spinner /> : (
            <div style={{ overflow:"auto", maxHeight:480 }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                <thead style={{ position:"sticky", top:0, background:"#1a1f2e" }}>
                  <tr style={{ color:"#64748b", borderBottom:"1px solid #2d3748" }}>
                    {["ID","Dept","Level","Risk","Band","Flight%","Anomaly","Top Feature"].map(h=>
                      <th key={h} style={{ padding:"8px 10px", textAlign:"left", fontWeight:500, whiteSpace:"nowrap" }}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r,i)=>(
                    <tr key={i} style={{ borderBottom:"1px solid #1e2533" }}>
                      <td style={{ padding:"6px 10px", fontFamily:"monospace", fontSize:10, color:"#94a3b8" }}>{r.employee_id?.slice(0,8)}…</td>
                      <td style={{ padding:"6px 10px" }}>{r.department}</td>
                      <td style={{ padding:"6px 10px", color:"#94a3b8" }}>{r.job_level}</td>
                      <td style={{ padding:"6px 10px", fontWeight:600, color: Number(r.latest_risk_index)>50?"#ef4444":"#f59e0b" }}>{Number(r.latest_risk_index).toFixed(1)}</td>
                      <td style={{ padding:"6px 10px" }}><BandBadge band={r.latest_risk_band}/></td>
                      <td style={{ padding:"6px 10px" }}>{(Number(r.flight_risk_prob)*100).toFixed(1)}%</td>
                      <td style={{ padding:"6px 10px", color:"#94a3b8" }}>{Number(r.anomaly_score).toFixed(3)}</td>
                      <td style={{ padding:"6px 10px", color:"#a78bfa", fontSize:11 }}>{r.shap_top_feature_1}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* SHAP feature chart */}
        <Card title="Top SHAP Features (sample)">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={shap} layout="vertical" margin={{ left:10 }}>
              <XAxis type="number" tick={{ fill:"#94a3b8", fontSize:10 }} />
              <YAxis type="category" dataKey="name" width={130} tick={{ fill:"#94a3b8", fontSize:10 }} />
              <Tooltip contentStyle={{ background:"#1a1f2e", border:"1px solid #2d3748" }} />
              <Bar dataKey="value" fill="#7c3aed" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
