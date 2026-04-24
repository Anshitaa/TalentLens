export function Card({ title, children, style = {} }) {
  return (
    <div style={{ background:"#18181b", borderRadius:10, padding:20, border:"1px solid #27272a", ...style }}>
      {title && (
        <div style={{ fontSize:11, fontWeight:600, color:"#71717a", textTransform:"uppercase",
          letterSpacing:"0.8px", marginBottom:16 }}>
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

export function KpiCard({ label, value, sub, color = "#6366f1" }) {
  return (
    <div style={{ background:"#18181b", borderRadius:10, padding:"18px 20px",
      border:"1px solid #27272a", borderTop:`2px solid ${color}` }}>
      <div style={{ fontSize:28, fontWeight:700, color:"#fafafa", letterSpacing:"-0.5px", lineHeight:1.2 }}>{value}</div>
      <div style={{ fontSize:12, color:"#71717a", marginTop:6, fontWeight:500 }}>{label}</div>
      {sub && <div style={{ fontSize:11, color:"#52525b", marginTop:3 }}>{sub}</div>}
    </div>
  );
}

export const BAND_COLOR = {
  Low:      "#22c55e",
  Medium:   "#f59e0b",
  High:     "#f97316",
  Critical: "#ef4444",
};

export function BandBadge({ band }) {
  const color = BAND_COLOR[band] ?? "#71717a";
  return (
    <span style={{
      background: color + "18",
      color,
      border: `1px solid ${color}30`,
      padding:"2px 8px", borderRadius:4,
      fontSize:11, fontWeight:600, letterSpacing:"0.3px",
    }}>
      {band}
    </span>
  );
}

export function Spinner() {
  return (
    <div style={{ color:"#52525b", padding:60, textAlign:"center", fontSize:13 }}>
      Loading…
    </div>
  );
}

export function ErrorMsg({ msg }) {
  return (
    <div style={{ color:"#f87171", padding:"16px 20px", background:"#1c0a0a",
      border:"1px solid #3f0f0f", borderRadius:8, fontSize:13 }}>
      {msg}
    </div>
  );
}

export const PAGE_TITLE = {
  fontSize: 20, fontWeight: 700, color: "#fafafa",
  letterSpacing: "-0.4px", margin: 0,
};

export const SECTION_GRID = (cols = "1fr 1fr") => ({
  display: "grid", gridTemplateColumns: cols, gap: 16,
});
