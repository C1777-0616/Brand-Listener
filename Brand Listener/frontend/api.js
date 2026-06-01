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
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  try { return new Date(isoStr).toLocaleString("zh-CN"); }
  catch { return isoStr; }
}

function shortId() {
  return Math.random().toString(36).substring(2, 8);
}

async function fetchEntryStats(days = 30, platform = '') {
  const params = new URLSearchParams({ days });
  if (platform) params.set('platform', platform);
  return api(`/api/entries/stats?${params}`);
}

async function fetchKeywordCloud(days = 30, limit = 50) {
  return api(`/api/entries/keyword-cloud?days=${days}&limit=${limit}`);
}

async function fetchEntryFeed(page = 1, perPage = 20, filters = {}) {
  const params = new URLSearchParams({ page, per_page: perPage });
  Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
  return api(`/api/entries/feed?${params}`);
}
