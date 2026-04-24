import { useState, useRef, useEffect } from "react";
import { agentChat } from "../api";
import { PAGE_TITLE } from "../components/Card";

const SUGGESTIONS = [
  "Which employees are at critical risk?",
  "What is our HR policy for high-risk employees?",
  "Generate a risk report for Engineering",
  "Show me the risk summary",
];

export default function AgentChatbot() {
  const [messages, setMessages] = useState([
    { role:"assistant", text:"Hi! I'm the TalentLens AI agent. I can query live risk data, search HR policies, and generate department reports. What would you like to know?" }
  ]);
  const [input,    setInput]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [provider, setProvider] = useState("gemini");
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [messages]);

  async function send(text) {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");
    setMessages(m => [...m, { role:"user", text:msg }]);
    setLoading(true);
    try {
      const res = await agentChat(msg, provider);
      setMessages(m => [...m, { role:"assistant", text: res.response, tools: res.tool_calls_used }]);
    } catch (e) {
      setMessages(m => [...m, { role:"assistant", text:`Error: ${e.response?.data?.detail || e.message}`, error:true }]);
    }
    setLoading(false);
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"calc(100vh - 48px)" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <h1 style={PAGE_TITLE}>AI Risk Agent</h1>
        <select value={provider} onChange={e=>setProvider(e.target.value)}
          style={{ background:"#18181b", border:"1px solid #27272a", color:"#a1a1aa", borderRadius:6, padding:"5px 10px", fontSize:12, outline:"none" }}>
          <option value="gemini">Gemini Flash (free)</option>
          <option value="anthropic">Claude (Anthropic)</option>
          <option value="openai">GPT-4o Mini</option>
          <option value="local">Ollama (local)</option>
        </select>
      </div>

      {/* Suggestions */}
      <div style={{ display:"flex", gap:8, flexWrap:"wrap", marginBottom:12 }}>
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={()=>send(s)} style={{ background:"#18181b", border:"1px solid #27272a",
            color:"#a1a1aa", borderRadius:6, padding:"5px 14px", fontSize:12, cursor:"pointer",
            fontFamily:"inherit" }}>
            {s}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflow:"auto", background:"#111113", borderRadius:8,
        border:"1px solid #27272a", padding:16, marginBottom:12 }}>
        {messages.map((m,i) => (
          <div key={i} style={{ marginBottom:16, display:"flex", flexDirection:"column",
            alignItems: m.role==="user" ? "flex-end" : "flex-start" }}>
            <div style={{ maxWidth:"80%",
              background: m.role==="user" ? "#1e1b4b" : (m.error ? "#1c0a0a" : "#18181b"),
              border: `1px solid ${m.role==="user" ? "#312e81" : (m.error ? "#3f0f0f" : "#27272a")}`,
              borderRadius:8, padding:"10px 16px", fontSize:13, lineHeight:1.7,
              color: m.error ? "#f87171" : "#e4e4e7", whiteSpace:"pre-wrap" }}>
              {m.text}
            </div>
            {m.tools?.length > 0 && (
              <div style={{ marginTop:4, fontSize:10, color:"#64748b" }}>
                Tools used: {m.tools.join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ color:"#94a3b8", fontSize:13, display:"flex", gap:4, alignItems:"center" }}>
            <span>Thinking</span>
            <span style={{ animation:"pulse 1s infinite" }}>…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display:"flex", gap:8 }}>
        <input value={input} onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>{ if(e.key==="Enter"&&!e.shiftKey){ e.preventDefault(); send(); }}}
          placeholder="Ask about risk scores, HR policies, or request a department report…"
          style={{ flex:1, background:"#18181b", border:"1px solid #27272a", color:"#fafafa",
            borderRadius:8, padding:"10px 14px", fontSize:13, outline:"none", fontFamily:"inherit" }} />
        <button onClick={()=>send()} disabled={loading||!input.trim()}
          style={{ background:"#6366f1", border:"none", color:"#fff", borderRadius:8,
            padding:"10px 24px", fontSize:13, fontWeight:600, cursor:loading?"not-allowed":"pointer",
            opacity: loading||!input.trim() ? 0.4 : 1, fontFamily:"inherit" }}>
          Send
        </button>
      </div>
    </div>
  );
}
