// Brand Listener - Shared API utility
const API_BASE = "";

async function api(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json();
}

async function fetchPipelineData() {
  const result = await api("/api/data/latest");
  return result.has_data ? result.data : {};
}

async function runPipeline() {
  return api("/api/pipeline/run", { method: "POST" });
}

async function uploadExport(file) {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch("/api/exports/upload", { method: "POST", body: formData });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}

async function listExports() {
  return api("/api/exports");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  try { return new Date(isoStr).toLocaleString("zh-CN"); }
  catch { return isoStr; }
}

function shortId() {
  return Math.random().toString(36).substring(2, 8);
}
