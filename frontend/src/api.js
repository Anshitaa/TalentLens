import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export const api = axios.create({ baseURL: BASE });

export const getRiskSummary    = ()           => api.get("/risk/summary").then(r => r.data);
export const getRiskTop        = ()           => api.get("/risk/top").then(r => r.data);
export const getRiskByDept     = ()           => api.get("/risk/department").then(r => r.data);
export const getRiskScores     = (params={}) => api.get("/risk/scores", { params }).then(r => r.data);
export const getEmployees      = (params={}) => api.get("/employees", { params }).then(r => r.data);
export const getEmployee       = (id)        => api.get(`/employees/${id}`).then(r => r.data);
export const getEmployeeScores = (id)        => api.get(`/risk/scores/${id}`).then(r => r.data);
export const getHiringFunnel   = ()          => api.get("/hiring/funnel").then(r => r.data);
export const getHiringSummary  = ()          => api.get("/hiring/summary").then(r => r.data);
export const getModelRuns      = ()          => api.get("/models/runs").then(r => r.data);
export const getDriftReports   = ()          => api.get("/audit/drift").then(r => r.data);
export const getOverrides      = ()          => api.get("/audit/overrides").then(r => r.data);
export const submitOverride    = (body)      => api.post("/audit/override", body).then(r => r.data);
export const agentChat         = (message, provider="anthropic") =>
  api.post("/agent/chat", { message, provider }).then(r => r.data);
export const narrateRisk       = (id)        => api.get(`/agent/narrate/${id}`).then(r => r.data);
