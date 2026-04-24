import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { LayoutDashboard, TrendingUp, ShieldCheck, Users, Bot } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import RiskExplorer from "./pages/RiskExplorer";
import ModelGovernance from "./pages/ModelGovernance";
import HiringFunnel from "./pages/HiringFunnel";
import AgentChatbot from "./pages/AgentChatbot";

const NAV = [
  { to: "/",           label: "Dashboard",     Icon: LayoutDashboard },
  { to: "/risk",       label: "Risk Explorer", Icon: TrendingUp       },
  { to: "/governance", label: "Governance",    Icon: ShieldCheck      },
  { to: "/hiring",     label: "Hiring Funnel", Icon: Users            },
  { to: "/agent",      label: "AI Agent",      Icon: Bot              },
];

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display:"flex", height:"100vh", fontFamily:"-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif", background:"#09090b", color:"#fafafa" }}>
        <nav style={{ width:220, background:"#111113", display:"flex", flexDirection:"column", borderRight:"1px solid #27272a", flexShrink:0 }}>
          <div style={{ padding:"20px 20px 16px", borderBottom:"1px solid #27272a" }}>
            <div style={{ fontSize:15, fontWeight:700, color:"#fafafa", letterSpacing:"-0.3px" }}>TalentLens</div>
            <div style={{ fontSize:11, color:"#52525b", marginTop:2, fontWeight:500 }}>Workforce Intelligence</div>
          </div>
          <div style={{ padding:"12px 8px", flex:1 }}>
            {NAV.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to} end={to === "/"}
                style={({ isActive }) => ({
                  display:"flex", alignItems:"center", gap:10,
                  padding:"8px 12px", borderRadius:6, marginBottom:2,
                  textDecoration:"none", fontSize:13, fontWeight:500,
                  transition:"all 0.1s",
                  color: isActive ? "#fafafa" : "#71717a",
                  background: isActive ? "#1c1c1f" : "transparent",
                })}>
                <Icon size={15} strokeWidth={isActive => isActive ? 2.5 : 1.8} />
                {label}
              </NavLink>
            ))}
          </div>
          <div style={{ padding:"12px 20px 16px", borderTop:"1px solid #27272a" }}>
            <div style={{ fontSize:10, color:"#3f3f46", fontWeight:500, textTransform:"uppercase", letterSpacing:"0.8px" }}>Phase 6 — Live</div>
          </div>
        </nav>
        <main style={{ flex:1, overflow:"auto", padding:"28px 32px", background:"#09090b" }}>
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/risk"       element={<RiskExplorer />} />
            <Route path="/governance" element={<ModelGovernance />} />
            <Route path="/hiring"     element={<HiringFunnel />} />
            <Route path="/agent"      element={<AgentChatbot />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
