// Jo web GUI app — polished chat UX (Claude/ChatGPT-inspired patterns)
const $ = (id) => document.getElementById(id);

const appShell = $("app-shell");
const chatLog = $("chat-log");
const chatCollection = $("chat-collection");
const chatEmpty = $("chat-empty");
const chatForm = $("chat-form");
const chatInput = $("chat-input");
const chatSend = $("chat-send");
const chatStop = $("chat-stop");
const chatStatus = $("chat-status");
const emptyGreeting = $("empty-greeting");
const apiBaseInput = $("api-base");
const modelSelect = $("model-select");
const newChatBtn = $("new-chat");
const sidebarToggle = $("sidebar-toggle");
const themeToggle = $("theme-toggle");
const brandHome = $("brand-home");
const mobileMenu = $("mobile-menu");
const sessionListEl = $("session-list");
const sessionSearchInput = $("session-search");
const chatTitle = $("chat-title");
const chatSubtitle = $("chat-subtitle");
const chatRefresh = $("chat-refresh");
const chatExport = $("chat-export");
const sidebarBackdrop = $("sidebar-backdrop");
const scrollBottomBtn = $("scroll-bottom");
const toastHost = $("toast-host");
const srStatus = $("sr-status");
const modelSearchInput = $("model-search");
const reconnectBanner = $("reconnect-banner");
const reconnectText = $("reconnect-text");
const reconnectBtn = $("reconnect-btn");

const openSettingsBtn = $("open-settings");
const openSettingsTop = $("open-settings-top");
const openSettingsFoot = $("open-settings-foot");
const settingsBackdrop = $("settings-backdrop");
const settingsModal = $("settings-modal");
const settingsClose = $("settings-close");
const settingsDone = $("settings-done");
const settingsRefresh = $("settings-refresh");
const settingsTheme = $("settings-theme");
const settingsClearBase = $("settings-clear-base");

const shortcutsBackdrop = $("shortcuts-backdrop");
const shortcutsModal = $("shortcuts-modal");
const shortcutsClose = $("shortcuts-close");

const backendStatusEl = $("backend-status");
const backendMeta = $("backend-meta");
const backendHint = $("backend-hint");
const statusDot = $("status-dot");
const sidebarConnDot = $("sidebar-conn-dot");
const modelPill = $("model-pill");
const modelPillLabel = $("model-pill-label");
const modelPillDot = $("model-pill-dot");
const modelInfo = $("model-info");

let busy = false;
let sessionSearchQuery = "";
let controller = null;
let sessions = [];
let currentSessionId = null;
let healthInfo = null;
let discoveredBase = "";

const SESSIONS_KEY = "jo.sessions.v1";
const CURRENT_KEY = "jo.currentSession.v1";
const API_KEY = "jo.apiBase";
const MODEL_KEY = "jo.model";

function uid() {
  return "web_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}
function now() { return Date.now(); }
function currentSession() { return sessions.find((s) => s.id === currentSessionId) || null; }
function getMessages() { const s = currentSession(); return s ? (s.messages || []) : []; }

function showToast(text) {
  if (!toastHost || !text) return;
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = text;
  toastHost.appendChild(t);
  setTimeout(() => {
    t.style.opacity = "0";
    t.style.transition = "opacity 180ms";
    setTimeout(() => t.remove(), 220);
  }, 1700);
}

function announce(text) {
  if (!srStatus) return;
  srStatus.textContent = "";
  setTimeout(() => { srStatus.textContent = text || ""; }, 30);
}

function saveState() {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, 60)));
    if (currentSessionId) localStorage.setItem(CURRENT_KEY, currentSessionId);
  } catch {}
}

function getSavedApiBase() {
  try { return (localStorage.getItem(API_KEY) || "").trim(); } catch { return ""; }
}
function getApiBase() {
  const manual = apiBaseInput ? apiBaseInput.value.trim().replace(/\/$/, "") : "";
  if (manual) return manual;
  return (discoveredBase || "").trim().replace(/\/$/, "");
}
function getSelectedModel() {
  try {
    const v = modelSelect && modelSelect.value ? String(modelSelect.value).trim() : "";
    if (v) return v;
  } catch {}
  try { return (localStorage.getItem(MODEL_KEY) || "auto").trim() || "auto"; } catch { return "auto"; }
}

function isMobileLayout() { return window.matchMedia && window.matchMedia("(max-width: 768px)").matches; }
function setSidebarOpen(open) {
  if (!appShell) return;
  if (isMobileLayout()) {
    appShell.classList.toggle("sidebar-open", !!open);
  } else {
    appShell.classList.remove("sidebar-open");
    appShell.classList.toggle("sidebar-collapsed", !open);
  }
}
function toggleSidebar() {
  if (!appShell) return;
  if (isMobileLayout()) setSidebarOpen(!appShell.classList.contains("sidebar-open"));
  else appShell.classList.toggle("sidebar-collapsed");
}
function syncSidebarForViewport() {
  if (!appShell) return;
  if (isMobileLayout()) {
    if (!appShell.dataset.mobileInit) {
      appShell.dataset.mobileInit = "1";
      appShell.classList.remove("sidebar-open");
    }
  } else {
    appShell.classList.remove("sidebar-open");
    if (!appShell.dataset.desktopInit) {
      appShell.dataset.desktopInit = "1";
      appShell.classList.remove("sidebar-collapsed");
    }
  }
}

/* Modals */
let lastFocus = null;
function openSettings() {
  if (!settingsModal || !settingsBackdrop) return;
  closeShortcuts();
  lastFocus = document.activeElement;
  settingsBackdrop.hidden = false;
  settingsModal.hidden = false;
  document.body.style.overflow = "hidden";
  checkHealth();
  const first = apiBaseInput || modelSelect || settingsClose;
  if (first) setTimeout(() => first.focus(), 0);
}
function closeSettings() {
  if (!settingsModal || !settingsBackdrop) return;
  settingsBackdrop.hidden = true;
  settingsModal.hidden = true;
  if (!isShortcutsOpen()) document.body.style.overflow = "";
  if (lastFocus && typeof lastFocus.focus === "function") { try { lastFocus.focus(); } catch {} }
}
function isSettingsOpen() { return settingsModal && !settingsModal.hidden; }

let shortcutsLastFocus = null;
function openShortcuts() {
  if (!shortcutsModal || !shortcutsBackdrop) return;
  closeSettings();
  shortcutsLastFocus = document.activeElement;
  shortcutsBackdrop.hidden = false;
  shortcutsModal.hidden = false;
  document.body.style.overflow = "hidden";
  if (shortcutsClose) setTimeout(() => shortcutsClose.focus(), 0);
}
function closeShortcuts() {
  if (!shortcutsModal || !shortcutsBackdrop) return;
  shortcutsBackdrop.hidden = true;
  shortcutsModal.hidden = true;
  if (!isSettingsOpen()) document.body.style.overflow = "";
  if (shortcutsLastFocus && typeof shortcutsLastFocus.focus === "function") { try { shortcutsLastFocus.focus(); } catch {} }
}
function isShortcutsOpen() { return shortcutsModal && !shortcutsModal.hidden; }

/* Markdown rendering */
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function sanitizeHref(href) {
  try {
    const u = new URL(href, location.href);
    if (["http:", "https:", "mailto:"].includes(u.protocol)) return u.href;
  } catch {}
  return "#";
}
function renderInline(text) {
  let s = escapeHtml(text);
  const codeSpans = [];
  s = s.replace(/`([^`\n]+)`/g, (_, c) => { const i = codeSpans.length; codeSpans.push("<code>" + c + "</code>"); return "\u0000C" + i + "\u0000"; });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => '<a href="' + escapeHtml(sanitizeHref(href)) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
  s = s.replace(/\*(?!\s)([^*\n]+?)\*(?!\*)/g, "<em>$1</em>");
  s = s.replace(/\u0000C(\d+)\u0000/g, (_, i) => codeSpans[Number(i)] || "");
  return s;
}
function renderMarkdown(text) {
  const src = String(text || "").replace(/\r\n/g, "\n");
  const parts = src.split(/```/);
  let html = "";
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      let code = parts[i]; let lang = "";
      const m = code.match(/^([^\n]*)\n/);
      if (m) { lang = (m[1] || "").trim(); code = code.slice(m[0].length); }
      const safe = escapeHtml(code.replace(/\n$/, ""));
      html += '<div class="code-wrap"><div class="code-head"><span>' + escapeHtml(lang || 'code') + '</span><button type="button" class="code-copy" data-code-copy>Copy</button></div><pre><code>' + safe + '</code></pre></div>';
      continue;
    }
    const lines = parts[i].split("\n"); let j = 0;
    while (j < lines.length) {
      const line = lines[j];
      if (!line.trim()) { j++; continue; }
      if (/^###\s+/.test(line)) { html += "<h3>" + renderInline(line.replace(/^###\s+/, "")) + "</h3>"; j++; continue; }
      if (/^##\s+/.test(line)) { html += "<h2>" + renderInline(line.replace(/^##\s+/, "")) + "</h2>"; j++; continue; }
      if (/^#\s+/.test(line)) { html += "<h1>" + renderInline(line.replace(/^#\s+/, "")) + "</h1>"; j++; continue; }
      if (/^(-{3,}|\*{3,})$/.test(line.trim())) { html += "<hr>"; j++; continue; }
      if (/^>\s?/.test(line)) {
        let bq = []; while (j < lines.length && /^>\s?/.test(lines[j])) { bq.push(lines[j].replace(/^>\s?/, "")); j++; }
        html += "<blockquote>" + renderInline(bq.join("\n")).replace(/\n/g, "<br>") + "</blockquote>"; continue;
      }
      if (/^(\*|-)\s+/.test(line)) {
        let items = []; while (j < lines.length && /^(\*|-)\s+/.test(lines[j])) { items.push("<li>" + renderInline(lines[j].replace(/^(\*|-)\s+/, "")) + "</li>"); j++; }
        html += "<ul>" + items.join("") + "</ul>"; continue;
      }
      if (/^\d+\.\s+/.test(line)) {
        let items = []; while (j < lines.length && /^\d+\.\s+/.test(lines[j])) { items.push("<li>" + renderInline(lines[j].replace(/^\d+\.\s+/, "")) + "</li>"); j++; }
        html += "<ol>" + items.join("") + "</ol>"; continue;
      }
      let para = [line]; j++;
      while (j < lines.length && lines[j].trim() && !/^(#{1,3}\s+|>\s?|(\*|-)\s+|\d+\.\s+|```|(-{3,}|\*{3,})$)/.test(lines[j])) { para.push(lines[j]); j++; }
      html += "<p>" + para.map(renderInline).join("<br>") + "</p>";
    }
  }
  return html || "&nbsp;";
}

function bindCopyButtons(root) {
  if (!root) return;
  root.querySelectorAll("[data-code-copy]").forEach((btn) => {
    if (btn._bound) return; btn._bound = true;
    btn.addEventListener("click", async () => {
      const wrap = btn.closest(".code-wrap");
      const code = wrap ? wrap.querySelector("code") : null;
      try {
        await navigator.clipboard.writeText(code ? code.textContent : "");
        btn.textContent = "Copied"; showToast("Code copied");
        setTimeout(() => (btn.textContent = "Copy"), 1200);
      } catch { btn.textContent = "Failed"; setTimeout(() => (btn.textContent = "Copy"), 1200); }
    });
  });
}

function renderContent(el, text, role, streaming) {
  if (role === "user") { el.textContent = text; return; }
  el.innerHTML = renderMarkdown(text);
  if (streaming) el.classList.add("streaming-caret"); else el.classList.remove("streaming-caret");
  bindCopyButtons(el);
}

function formatTime(ts) {
  try { return ts ? new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : ""; } catch { return ""; }
}

function clearChatView() {
  if (!chatCollection) return;
  Array.from(chatCollection.children).forEach((n) => { if (n !== chatEmpty) n.remove(); });
}
function showEmpty() { if (chatEmpty) chatEmpty.style.display = "flex"; }
function hideEmpty() { if (chatEmpty) chatEmpty.style.display = "none"; }

function scrollToBottom(force) {
  if (!chatLog) return;
  const near = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight < 140;
  if (force || near) chatLog.scrollTop = chatLog.scrollHeight;
  updateScrollButton();
}
function updateScrollButton() {
  if (!scrollBottomBtn || !chatLog) return;
  const near = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight < 140;
  scrollBottomBtn.hidden = near || (getMessages().length === 0 && !busy);
}

function makeAvatar(role) {
  const a = document.createElement("div");
  a.className = "avatar";
  if (role === "assistant") {
    a.innerHTML = '<svg viewBox="0 0 32 32" width="16" height="16" fill="none"><circle cx="16" cy="16" r="10" stroke="currentColor" stroke-width="3.5"/><circle cx="25" cy="7" r="4" fill="var(--accent)"/></svg>';
  } else {
    a.textContent = "You";
  }
  return a;
}

function addMessageEl(role, content, opts = {}) {
  if (!opts.skipStore) hideEmpty();
  const msg = document.createElement("article");
  msg.className = "message " + (role === "user" ? "message-user" : "message-assistant") + (opts.error ? " message-error" : "");
  if (typeof opts.index === "number") msg.dataset.index = String(opts.index);

  const inner = document.createElement("div"); inner.className = "message-inner";
  if (role === "assistant") inner.appendChild(makeAvatar(role));

  const bodyWrap = document.createElement("div"); bodyWrap.className = "message-body";
  if (role === "assistant") {
    const roleEl = document.createElement("div"); roleEl.className = "message-role"; roleEl.textContent = "Jo"; bodyWrap.appendChild(roleEl);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble " + (role === "assistant" ? "message-content message-text" : "message-text");
  renderContent(bubble, content, role, !!opts.streaming);
  bodyWrap.appendChild(bubble);

  const footer = document.createElement("div"); footer.className = "message-footer";
  const t = formatTime(opts.ts);
  if (t) { const meta = document.createElement("span"); meta.className = "message-meta"; meta.textContent = t; footer.appendChild(meta); }
  if (role === "assistant" && opts.meta) {
    const info = [];
    if (opts.meta.provider) info.push(String(opts.meta.provider));
    if (opts.meta.model) info.push(String(opts.meta.model));
    if (typeof opts.meta.elapsed_ms === "number") info.push((opts.meta.elapsed_ms/1000).toFixed(opts.meta.elapsed_ms < 10000 ? 1 : 0) + "s");
    if (info.length) {
      const chip = document.createElement("span"); chip.className = "msg-chip"; chip.textContent = info.join(" · ");
      const degraded = ["fallback", "error", "unavailable", "system"].includes(String(opts.meta.provider || "").toLowerCase()) || String(opts.meta.model || "").toLowerCase() === "unavailable";
      if (degraded) chip.classList.add("msg-chip-warn");
      chip.title = `Provider: ${opts.meta.provider || "?"}\nModel: ${opts.meta.model || "?"}${typeof opts.meta.elapsed_ms === "number" ? `\nLatency: ${opts.meta.elapsed_ms} ms` : ""}${degraded ? "\nStatus: degraded/fallback response" : ""}`;
      footer.appendChild(chip);
    }
  }
  const actions = document.createElement("div"); actions.className = "message-actions";
  if (role === "user") {
    actions.appendChild(actionBtn("Edit", () => { if (busy) return; chatInput.value = content; autoResize(); chatInput.focus(); showToast("Edit, then send to resend"); }));
    actions.appendChild(actionBtn("Resend", () => { if (!busy) resendFromIndex(typeof opts.index === "number" ? opts.index : -1, content); }, true));
  } else {
    actions.appendChild(actionBtn("Copy", async (btn) => {
      try { await navigator.clipboard.writeText(content); btn.textContent = "Copied"; showToast("Copied"); setTimeout(()=>btn.textContent="Copy",1200); } catch { showToast("Copy failed"); }
    }));
    if (opts.canRegenerate) actions.appendChild(actionBtn("Regenerate", () => { if (!busy) regenerateLast(); }, true));
  }
  footer.appendChild(actions);
  bodyWrap.appendChild(footer);

  inner.appendChild(bodyWrap);
  msg.appendChild(inner);
  chatCollection.appendChild(msg);
  if (!opts.skipStore) scrollToBottom(false);
  return { msg, bubble };
}
function actionBtn(label, onClick, primary=false) {
  const b = document.createElement("button"); b.type = "button"; b.className = "msg-action" + (primary ? " primary" : ""); b.textContent = label;
  b.addEventListener("click", () => onClick(b));
  return b;
}

function renderMessages() {
  clearChatView();
  const msgs = getMessages();
  if (!msgs.length) { showEmpty(); updateScrollButton(); return; }
  hideEmpty();
  msgs.forEach((m, i) => {
    const isLastAssistant = m.role !== "user" && i === msgs.length - 1;
    addMessageEl(m.role, m.content, { error: !!m.error, skipStore: true, ts: m.ts, index: i, canRegenerate: isLastAssistant, meta: m.meta || null });
  });
  scrollToBottom(true);
}

function ensureSession() {
  let s = currentSession();
  if (!s) s = createSession(false);
  return s;
}
function pushMessage(role, content, error, meta) {
  const s = ensureSession();
  s.messages = s.messages || [];
  const m = { role, content, error: !!error, ts: now() };
  if (meta && typeof meta === "object") m.meta = meta;
  s.messages.push(m);
  if (role === "user" && (!s.title || s.title === "New chat")) s.title = content.trim().slice(0, 42) || "New chat";
  s.updatedAt = now();
  saveState(); renderSessionList(); updateHeader();
}

function createSession(switchTo = true) {
  const s = { id: uid(), title: "New chat", messages: [], createdAt: now(), updatedAt: now() };
  sessions.unshift(s);
  if (switchTo) { currentSessionId = s.id; renderMessages(); }
  saveState(); renderSessionList(); updateHeader();
  return s;
}
function switchSession(id) {
  currentSessionId = id; saveState(); renderSessionList(); renderMessages(); updateHeader();
  if (isMobileLayout()) setSidebarOpen(false);
  if (chatInput) chatInput.focus();
}

function renderSessionList() {
  if (!sessionListEl) return;
  sessionListEl.innerHTML = "";
  const q = (sessionSearchQuery || "").trim().toLowerCase();
  let list = [...sessions].sort((a,b) => (b.updatedAt||0)-(a.updatedAt||0));
  if (q) list = list.filter(s => ((s.title||"New chat")+" "+(s.messages||[]).map(m=>m.content||"").join(" ")).toLowerCase().includes(q));
  for (const s of list) {
    const item = document.createElement("button"); item.type = "button";
    item.className = "session-item" + (s.id === currentSessionId ? " active" : "");
    const textWrap = document.createElement("span"); textWrap.className = "session-text";
    const title = document.createElement("span"); title.className = "session-title"; title.textContent = s.title || "New chat";
    const meta = document.createElement("span"); meta.className = "session-meta";
    try { const t = s.updatedAt || s.createdAt; if (t) meta.textContent = new Date(t).toLocaleDateString(undefined,{month:"short",day:"numeric"}); } catch {}
    textWrap.appendChild(title); if (meta.textContent) textWrap.appendChild(meta);
    const actions = document.createElement("span"); actions.className = "session-actions";
    actions.appendChild(sessionAction("✎", "Rename", (e) => { e.stopPropagation(); inlineRename(s, textWrap); }));
    actions.appendChild(sessionAction("×", "Delete", (e) => {
      e.stopPropagation();
      sessions = sessions.filter(x => x.id !== s.id);
      if (currentSessionId === s.id) {
        if (sessions.length) switchSession(sessions[0].id); else createSession(true);
      }
      saveState(); renderSessionList(); updateHeader();
    }));
    item.appendChild(textWrap); item.appendChild(actions);
    item.addEventListener("click", () => switchSession(s.id));
    sessionListEl.appendChild(item);
  }
}
function sessionAction(text, title, onClick) {
  const b = document.createElement("span"); b.className = "session-action-btn"; b.title = title; b.textContent = text; b.addEventListener("click", onClick); return b;
}
function inlineRename(s, textWrap) {
  const input = document.createElement("input"); input.className = "session-rename-input"; input.value = s.title || "New chat";
  textWrap.innerHTML = ""; textWrap.appendChild(input); input.focus(); input.select();
  const commit = () => { s.title = (input.value||"").trim() || "New chat"; s.updatedAt = now(); saveState(); renderSessionList(); updateHeader(); };
  input.addEventListener("blur", commit, { once: true });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); input.blur(); } if (e.key === "Escape") { e.preventDefault(); renderSessionList(); } });
}

function resendFromIndex(index, content) {
  const s = ensureSession(); if (!s) return;
  let idx = index;
  if (idx < 0 || idx >= (s.messages||[]).length) {
    idx = -1; for (let i=(s.messages||[]).length-1;i>=0;i--) if (s.messages[i].role==="user" && s.messages[i].content===content) { idx=i; break; }
  }
  if (idx < 0) return;
  s.messages = s.messages.slice(0, idx); s.updatedAt = now(); saveState(); renderMessages(); renderSessionList(); updateHeader();
  chatInput.value = content; autoResize(); sendMessage();
}
function regenerateLast() {
  const s = ensureSession(); if (!s || !Array.isArray(s.messages) || busy) return;
  let lastUserIdx = -1; for (let i=s.messages.length-1;i>=0;i--) if (s.messages[i].role==="user") { lastUserIdx=i; break; }
  if (lastUserIdx < 0) return;
  const content = s.messages[lastUserIdx].content || "";
  s.messages = s.messages.slice(0, lastUserIdx); s.updatedAt = now(); saveState(); renderMessages(); renderSessionList(); updateHeader();
  chatInput.value = content; autoResize(); sendMessage();
}

/* Model + health */
function renderModelOptions() {
  if (!modelSelect) return;
  const current = getSelectedModel();
  const q = (modelSearchQuery || "").trim().toLowerCase();
  let list = Array.isArray(allModels) ? [...allModels] : [];
  // ensure auto first
  const auto = { id: "auto", label: "Auto (recommended, OmniRoute-first)", provider: "auto" };
  const filtered = list.filter(m => {
    const id = String(m.id || ""); if (id === "auto") return false;
    if (!q) return true;
    const hay = (id + " " + (m.label||"") + " " + (m.provider||"")).toLowerCase();
    return hay.includes(q);
  });
  // group by provider
  const groups = new Map();
  for (const m of filtered) {
    const p = (m.provider || "other").toLowerCase();
    if (!groups.has(p)) groups.set(p, []);
    groups.get(p).push(m);
  }
  const order = ["omniroute", "local", "openrouter", "nvidia", "doubleword", "pollinations", "auto", "other"];
  const keep = new Set();
  modelSelect.innerHTML = "";
  const addOpt = (parent, id, label) => {
    if (!id || keep.has(id)) return;
    keep.add(id);
    const opt = document.createElement("option");
    opt.value = id; opt.textContent = label || id;
    parent.appendChild(opt);
  };
  addOpt(modelSelect, auto.id, auto.label);
  for (const key of order) {
    if (!groups.has(key)) continue;
    const items = groups.get(key);
    if (!items.length) continue;
    const og = document.createElement("optgroup");
    og.label = key.charAt(0).toUpperCase() + key.slice(1);
    for (const m of items) addOpt(og, String(m.id), m.label || String(m.id));
    if (og.children.length) modelSelect.appendChild(og);
  }
  // any remaining groups
  for (const [key, items] of groups.entries()) {
    if (order.includes(key)) continue;
    const og = document.createElement("optgroup");
    og.label = key.charAt(0).toUpperCase() + key.slice(1);
    for (const m of items) addOpt(og, String(m.id), m.label || String(m.id));
    if (og.children.length) modelSelect.appendChild(og);
  }
  let target = current || "auto";
  if (!keep.has(target)) target = "auto";
  modelSelect.value = target;
  if (modelInfo) {
    const count = Math.max(0, keep.size - 1);
    const suffix = q ? ` (filtered from ${Math.max(0, (allModels||[]).filter(m=>m.id!=="auto").length)})` : "";
    modelInfo.textContent = count > 0 ? `${count} model option(s) shown${suffix}.` : "No models match the current filter.";
  }
}

async function refreshModels() {
  if (!modelSelect) return;
  const base = getApiBase(); if (!base) return;
  try {
    const res = await fetch(base + "/v1/models", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const models = Array.isArray(data.models) ? data.models : [];
    // normalize and dedupe
    const seen = new Set();
    const norm = [];
    for (const m of models) {
      const id = m && (m.id || m.name) ? String(m.id || m.name) : "";
      if (!id || seen.has(id)) continue;
      seen.add(id);
      norm.push({ id, provider: m.provider || "other", label: m.label || id });
    }
    if (!seen.has("auto")) norm.unshift({ id: "auto", provider: "auto", label: "Auto (recommended, OmniRoute-first)" });
    allModels = norm;
    renderModelOptions();
  } catch {}
}

function setConnState(state) {
  // state: ok | warn | err | idle
  if (sidebarConnDot) {
    sidebarConnDot.className = "quick-dot" + (state === "ok" ? " ok" : state === "err" ? " err" : "");
    sidebarConnDot.title = state === "ok" ? "Connected" : state === "err" ? "Connection issue" : "Checking connection";
  }
  if (statusDot) statusDot.className = "status-dot" + (state === "ok" ? " ok" : state === "err" ? " err" : "");
  if (modelPillDot) modelPillDot.className = "model-pill-dot" + (state === "ok" ? " ok" : "");
}

function updateHeader() {
  const s = currentSession();
  if (chatTitle) chatTitle.textContent = s ? (s.title || "Chat") : "New chat";
  const base = getApiBase();
  const selected = getSelectedModel();
  if (modelPillLabel) modelPillLabel.textContent = selected === "auto" ? "Auto" : selected;
  if (!base) {
    if (chatSubtitle) { chatSubtitle.textContent = "Waiting for backend…"; chatSubtitle.dataset.state = "idle"; }
    if (backendStatusEl) backendStatusEl.textContent = "Status: set API base URL or wait for auto-discovery";
    if (backendMeta) backendMeta.textContent = "";
    setConnState("idle");
    return;
  }
  if (healthInfo && healthInfo.status === "ok") {
    const configured = !!(healthInfo.configured || (healthInfo.keys && Object.values(healthInfo.keys).some(Boolean)));
    const provider = healthInfo.provider || "backend";
    const effective = healthInfo.model ? String(healthInfo.model) : "auto";
    const parts = [provider];
    if (effective && effective !== "auto") parts.push(effective);
    if (healthInfo.local_reachable) parts.push("local fallback ready");
    if (chatSubtitle) { chatSubtitle.textContent = (configured ? "Ready · " : "Reachable · ") + parts.slice(0,3).join(" · "); chatSubtitle.dataset.state = configured ? "ok" : "warn"; }
    if (backendStatusEl) backendStatusEl.textContent = configured ? "Status: online" : "Status: reachable (no model configured)";
    if (backendMeta) {
      const meta = [];
      if (healthInfo.provider) meta.push("provider: " + healthInfo.provider);
      if (healthInfo.model) meta.push("effective model: " + healthInfo.model);
      meta.push("selected: " + (selected || "auto"));
      if (healthInfo.omniroute_reachable) meta.push("omniroute: reachable");
      else if (healthInfo.keys && healthInfo.keys.omniroute_configured) meta.push("omniroute: unreachable");
      if (healthInfo.local_reachable) meta.push("local: ready");
      if (healthInfo.keys) {
        const k = Object.keys(healthInfo.keys).filter(x => healthInfo.keys[x]); if (k.length) meta.push("keys/config: " + k.join(", "));
      }
      if (!getSavedApiBase() && discoveredMeta) {
        const dm = [];
        if (discoveredMeta.updatedAt) dm.push("updated " + discoveredMeta.updatedAt);
        if (discoveredMeta.commit) dm.push("commit " + String(discoveredMeta.commit).slice(0, 7));
        if (discoveredMeta.runId) dm.push("run " + discoveredMeta.runId);
        if (dm.length) meta.push("backend: " + dm.join(", "));
      }
      backendMeta.textContent = meta.join(" · ");
    }
    if (backendHint) {
      if (healthInfo.keys && healthInfo.keys.omniroute_configured && !healthInfo.omniroute_reachable && !healthInfo.local_reachable) {
        backendHint.textContent = "OmniRoute is configured but unreachable; backend will use direct/fallback providers when available (responses may be degraded depending on upstreams).";
      } else if (!configured) {
        backendHint.textContent = "Backend is reachable but no model/provider appears configured. Set provider keys or enable OmniRoute/local backend.";
      } else {
        backendHint.textContent = "";
      }
    }
    setConnState(configured ? "ok" : "warn");
  } else {
    if (chatSubtitle) { chatSubtitle.textContent = "Connecting to backend…"; chatSubtitle.dataset.state = "err"; }
    if (backendStatusEl) backendStatusEl.textContent = "Status: checking/unreachable";
    setConnState("err");
  }
}

async function checkHealth() {
  const base = getApiBase();
  if (backendHint) backendHint.textContent = "";
  if (!base) { healthInfo = null; updateHeader(); return; }
  if (backendStatusEl) backendStatusEl.textContent = "Status: checking…";
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 7000);
  try {
    const res = await fetch(base + "/health", { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    let data = null;
    if ((res.headers.get("content-type")||"").includes("application/json")) { try { data = await res.json(); } catch {} }
    if (res.ok) {
      healthInfo = data || { status: "ok" };
      refreshModels().catch(()=>{});
    } else {
      healthInfo = null;
      if (backendStatusEl) backendStatusEl.textContent = "Status: HTTP " + res.status;
      if (backendHint) backendHint.textContent = "Backend responded but /health is not OK. Check server logs and endpoint.";
    }
  } catch (e) {
    clearTimeout(t);
    healthInfo = null;
    let msg = "Status: unreachable";
    if (location.protocol === "https:" && /^http:\/\//i.test(base)) msg = "Status: blocked (mixed content) — use HTTPS backend";
    else if (/^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i.test(base) && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") msg = "Status: unreachable (local URL from hosted GUI)";
    if (backendStatusEl) backendStatusEl.textContent = msg;
    if (backendHint) backendHint.textContent = "If using hosted GUI, set a public HTTPS API base (or wait for auto-discovery from backend.json).";
    // auto-recovery attempt for rotated/unreachable backend (non-invasive)
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => { attemptReconnect(true).catch(()=>{}); }, 2500);
  }
  if (healthInfo && healthInfo.status === "ok") hideReconnectBanner();
  updateHeader();
}

let healthPollTimer = null;
function startHealthPolling() {
  if (healthPollTimer) clearInterval(healthPollTimer);
  healthPollTimer = setInterval(() => {
    if (busy) return;
    if (!getApiBase()) return;
    checkHealth().catch(() => {});
  }, 30000);
}

async function discoverBackend(force = false) {
  const saved = getSavedApiBase();
  if (saved && !force) return false; // respect manual setting unless forced reconnect
  try {
    const res = await fetch("./backend.json", { cache: "no-store" });
    if (!res.ok) return false;
    const data = await res.json();
    const url = ((data && (data.apiBase || data.api_base || data.url)) || "").toString().trim().replace(/\/$/, "");
    const prev = discoveredBase;
    if (url) {
      discoveredBase = url;
      discoveredMeta = data && typeof data === "object" ? data : null;
      if (prev && prev !== url) showToast("Backend endpoint updated");
      return true;
    }
  } catch {}
  return false;
}

function showReconnectBanner(msg) {
  if (!reconnectBanner) return;
  if (reconnectText) reconnectText.textContent = msg || "Backend unreachable or rotated. Trying to reconnect…";
  reconnectBanner.hidden = false;
}
function hideReconnectBanner() { if (reconnectBanner) reconnectBanner.hidden = true; }
async function attemptReconnect(auto = false) {
  const base = getApiBase();
  // try to rediscover only when using discovered backend or no manual base
  const manual = getSavedApiBase();
  if (!manual) {
    const found = await discoverBackend(true);
    if (found) showReconnectBanner(auto ? "Found updated backend URL. Reconnecting…" : "Found backend URL. Reconnecting…");
  } else if (auto) {
    showReconnectBanner("Backend unreachable. Check your saved API base or clear it to re-enable auto-discovery.");
    return;
  }
  await checkHealth();
  if (healthInfo && healthInfo.status === "ok") {
    hideReconnectBanner();
    if (!auto) showToast("Reconnected");
  }
}

/* Chat transport */
async function sendToJo(message, signal, onDelta) {
  const base = getApiBase();
  const s = ensureSession();
  const history = (s.messages || []).slice(-20).map(m => ({ role: m.role, content: m.content }));
  const selectedModel = getSelectedModel();
  // try streaming
  try {
    const res = await fetch(base + "/v1/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
      body: JSON.stringify({ message, history, session_id: s.id, model: selectedModel }),
      signal,
    });
    if (res.ok && res.body && (res.headers.get("content-type")||"").includes("text/event-stream")) {
      const reader = res.body.getReader(); const decoder = new TextDecoder();
      let buffer = ""; let full = ""; let meta = null;
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n"); buffer = parts.pop() || "";
        for (const part of parts) {
          for (const line of part.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const data = line.slice(5).trim(); if (!data) continue;
            let evt; try { evt = JSON.parse(data); } catch { continue; }
            if (evt.session_id && evt.session_id !== s.id) { const old=s.id; s.id=evt.session_id; if (currentSessionId===old) currentSessionId=s.id; saveState(); }
            if (evt.error) throw new Error(evt.error);
            if (typeof evt.delta === "string") { full += evt.delta; if (onDelta) onDelta(full); }
            if (evt.done) {
              if (typeof evt.response === "string") { full = evt.response; if (onDelta) onDelta(full); }
              meta = { provider: evt.provider, model: evt.model, elapsed_ms: evt.elapsed_ms };
            }
          }
        }
      }
      return { text: full || "(empty response)", meta };
    }
  } catch (e) { if (e && e.name === "AbortError") throw e; }

  const response = await fetch(base + "/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, session_id: s.id, model: selectedModel }),
    signal,
  });
  if (!response.ok) throw new Error("HTTP " + response.status);
  const contentType = response.headers.get("content-type") || "";
  let content = await response.text();
  let meta = null;
  if (contentType.includes("application/json")) {
    try {
      const data = JSON.parse(content);
      if (data.session_id && data.session_id !== s.id) { const old=s.id; s.id=data.session_id; if (currentSessionId===old) currentSessionId=s.id; saveState(); }
      content = data.response || data.message || data.content || data.reply || (typeof data === "string" ? data : JSON.stringify(data));
      meta = { provider: data.provider, model: data.model, elapsed_ms: data.elapsed_ms };
    } catch {}
  }
  return { text: content || "(empty response)", meta };
}

function setBusyThinking(on) {
  busy = on;
  if (chatSend) chatSend.disabled = on || !chatInput.value.trim();
  if (chatStop) chatStop.hidden = !on;
  if (chatStatus) chatStatus.textContent = on ? "Responding…" : "";
  announce(on ? "Assistant is responding" : "Response complete");
  updateScrollButton();
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || busy) return;
  const base = getApiBase();
  ensureSession();
  if (!base) {
    pushMessage("user", text, false); addMessageEl("user", text, { skipStore: true, ts: now(), index: getMessages().length-1 });
    chatInput.value = ""; autoResize();
    const em = 'No backend configured. Open Settings to set an API base URL (or wait for auto-discovery), then try again. GET <API_BASE>/health should be reachable.';
    pushMessage("assistant", em, true); renderMessages(); openSettings(); checkHealth(); return;
  }

  pushMessage("user", text, false);
  const userIdx = getMessages().length - 1;
  addMessageEl("user", text, { skipStore: true, ts: getMessages()[userIdx].ts, index: userIdx });
  chatInput.value = ""; autoResize();
  setBusyThinking(true);
  controller = new AbortController();

  let streamMsg = null; let streamBubble = null;
  try {
    hideEmpty();
    streamMsg = document.createElement("article"); streamMsg.className = "message message-assistant"; streamMsg.setAttribute("aria-busy", "true");
    const inner = document.createElement("div"); inner.className = "message-inner"; inner.appendChild(makeAvatar("assistant"));
    const bodyWrap = document.createElement("div"); bodyWrap.className = "message-body";
    const roleEl = document.createElement("div"); roleEl.className = "message-role"; roleEl.textContent = "Jo"; bodyWrap.appendChild(roleEl);
    streamBubble = document.createElement("div"); streamBubble.className = "bubble message-content message-text streaming-caret"; streamBubble.textContent = "";
    bodyWrap.appendChild(streamBubble); inner.appendChild(bodyWrap); streamMsg.appendChild(inner);
    chatCollection.appendChild(streamMsg); scrollToBottom(true);

    let finalText = ""; let finalMeta = null;
    const result = await sendToJo(text, controller.signal, (partial) => {
      finalText = partial; renderContent(streamBubble, partial, "assistant", true); scrollToBottom(false);
    });
    finalText = (result && result.text) || finalText || "(empty response)";
    finalMeta = result && result.meta ? result.meta : null;
    if (streamMsg && streamMsg.parentNode) streamMsg.remove(); streamMsg = null;
    pushMessage("assistant", finalText, false, finalMeta);
    renderMessages();
  } catch (error) {
    if (streamMsg && streamMsg.parentNode) streamMsg.remove();
    if (error && error.name === "AbortError") {
      pushMessage("assistant", "Stopped.", true);
    } else {
      let em = "Could not reach Jo backend: " + (error && error.message ? error.message : String(error));
      const isNetwork = error && (error.name === "TypeError" || /NetworkError|Failed to fetch|fetch resource/i.test(String((error && error.message) || error)));
      if (isNetwork) {
        const hints = [];
        if (location.protocol === "https:" && /^http:\/\//i.test(base)) hints.push("page is HTTPS but API base is HTTP (mixed content blocked) — use an HTTPS backend URL");
        if (/^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i.test(base) && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") hints.push("API base points to localhost but you're on hosted GUI — deploy backend or open GUI locally");
        hints.push("check backend is running and /health responds");
        em += "\n\nHints:\n- " + hints.join("\n- ");
      }
      pushMessage("assistant", em, true);
    }
    renderMessages();
  } finally {
    controller = null; setBusyThinking(false); refreshModels().catch(()=>{}); checkHealth().catch(()=>{});
  }
}

/* Composer */
function autoResize() {
  if (!chatInput) return;
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
  if (chatSend) chatSend.disabled = busy || !chatInput.value.trim();
}

/* Theme */
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#181818" : "#f7f7f8");
  try { localStorage.setItem("jo.theme", theme); } catch {}
}
function toggleTheme() { setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); }

function getGreeting(date) {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "Good morning";
  if (h >= 12 && h < 18) return "Good afternoon";
  if (h >= 18 && h < 23) return "Good evening";
  return "Good night";
}

/* State */
function loadState() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (raw) { const data = JSON.parse(raw); if (Array.isArray(data)) sessions = data.filter(s => s && s.id && Array.isArray(s.messages)); }
  } catch { sessions = []; }
  try { const cid = localStorage.getItem(CURRENT_KEY); if (cid && sessions.some(s => s.id === cid)) currentSessionId = cid; } catch {}
  if (!currentSessionId && sessions.length) currentSessionId = sessions[0].id;
  if (!sessions.length) createSession(true);
  // migrate legacy wrong default
  try { const saved = localStorage.getItem(API_KEY); if (saved && /ouroboros-agent\.ai/i.test(saved)) { localStorage.removeItem(API_KEY); if (apiBaseInput) apiBaseInput.value = ""; } } catch {}
}

function exportCurrentChat() {
  const s = currentSession();
  if (!s || !(s.messages || []).length) { showToast("No messages to export"); return; }
  const title = (s.title || "chat").replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "-").slice(0, 60) || "chat";
  const lines = [`# ${s.title || "Chat"}`, "", `Exported: ${new Date().toISOString()}`, `Backend: ${getApiBase() || "(not set)"}`, ""];
  for (const m of (s.messages || [])) {
    const role = m.role === "user" ? "User" : "Jo";
    const when = m.ts ? new Date(m.ts).toLocaleString() : "";
    let metaStr = "";
    if (m.role !== "user" && m.meta) {
      const bits = [m.meta.provider, m.meta.model].filter(Boolean);
      if (typeof m.meta.elapsed_ms === "number") bits.push(`${m.meta.elapsed_ms}ms`);
      if (bits.length) metaStr = ` [${bits.join(" · ")}]`;
    }
    lines.push(`## ${role}${when ? ` (${when})` : ""}${metaStr}`, "", String(m.content || ""), "");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${title}.md`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast("Chat exported");
}

/* Events */
function bindEvents() {
  if (chatForm) chatForm.addEventListener("submit", (e) => { e.preventDefault(); sendMessage(); });
  if (chatInput) {
    chatInput.addEventListener("input", autoResize);
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy && chatInput.value.trim()) chatForm.requestSubmit(); }
    });
  }
  if (chatStop) chatStop.addEventListener("click", () => { if (controller) controller.abort(); });
  if (chatRefresh) chatRefresh.addEventListener("click", () => { showToast("Refreshing connection…"); checkHealth(); });
  if (chatExport) chatExport.addEventListener("click", exportCurrentChat);
  if (scrollBottomBtn) scrollBottomBtn.addEventListener("click", () => scrollToBottom(true));
  if (chatLog) chatLog.addEventListener("scroll", updateScrollButton, { passive: true });
  if (reconnectBtn) reconnectBtn.addEventListener("click", () => { showToast("Reconnecting…"); attemptReconnect(false).catch(()=>{}); });
  if (modelSearchInput) modelSearchInput.addEventListener("input", () => { modelSearchQuery = modelSearchInput.value || ""; renderModelOptions(); });

  document.querySelectorAll(".suggest-card[data-prompt], .tip-chip[data-prompt]").forEach((btn) => {
    btn.addEventListener("click", () => { const p = btn.getAttribute("data-prompt") || ""; if (!p) return; chatInput.value = p; autoResize(); chatInput.focus(); });
  });

  if (newChatBtn) newChatBtn.addEventListener("click", () => { createSession(true); if (chatInput) { chatInput.value = ""; autoResize(); chatInput.focus(); } if (isMobileLayout()) setSidebarOpen(false); });
  if (brandHome) brandHome.addEventListener("click", () => { if (chatInput) chatInput.focus(); });

  if (sidebarToggle) sidebarToggle.addEventListener("click", toggleSidebar);
  if (mobileMenu) mobileMenu.addEventListener("click", toggleSidebar);
  if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", () => setSidebarOpen(false));
  window.addEventListener("resize", () => { clearTimeout(window.__joResizeT); window.__joResizeT = setTimeout(syncSidebarForViewport, 80); });

  if (themeToggle) themeToggle.addEventListener("click", toggleTheme);
  if (settingsTheme) settingsTheme.addEventListener("click", () => { toggleTheme(); showToast("Theme updated"); });

  if (sessionSearchInput) sessionSearchInput.addEventListener("input", () => { sessionSearchQuery = sessionSearchInput.value || ""; renderSessionList(); });

  // Modals
  [openSettingsBtn, openSettingsTop, openSettingsFoot, modelPill].forEach((el) => { if (el) el.addEventListener("click", openSettings); });
  [settingsBackdrop, settingsClose, settingsDone].forEach((el) => { if (el) el.addEventListener("click", closeSettings); });
  [shortcutsBackdrop, shortcutsClose].forEach((el) => { if (el) el.addEventListener("click", closeShortcuts); });
  if (settingsRefresh) settingsRefresh.addEventListener("click", () => { showToast("Refreshing…"); checkHealth(); });
  if (settingsClearBase) settingsClearBase.addEventListener("click", () => {
    try { localStorage.removeItem(API_KEY); } catch {}
    if (apiBaseInput) apiBaseInput.value = "";
    discoveredBase = "";
    healthInfo = null;
    showToast("Saved API base cleared");
    discoverBackend().finally(() => checkHealth());
  });

  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;
    const tag = (e.target && e.target.tagName) || "";
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (e.target && e.target.isContentEditable);

    if (e.key === "Escape") {
      if (isShortcutsOpen()) { e.preventDefault(); closeShortcuts(); return; }
      if (isSettingsOpen()) { e.preventDefault(); closeSettings(); return; }
      if (busy && controller) { e.preventDefault(); controller.abort(); return; }
      if (isMobileLayout() && appShell && appShell.classList.contains("sidebar-open")) { setSidebarOpen(false); return; }
    }
    if (mod && e.key === ",") { e.preventDefault(); openSettings(); return; }
    if (mod && e.shiftKey && (e.key === "O" || e.key === "o")) { e.preventDefault(); createSession(true); if (chatInput) { chatInput.value=""; autoResize(); chatInput.focus(); } return; }
    if (mod && (e.key === "k" || e.key === "K")) { e.preventDefault(); if (sessionSearchInput) { if (isMobileLayout()) setSidebarOpen(true); sessionSearchInput.focus(); sessionSearchInput.select(); } return; }
    if (mod && e.key === "/") { e.preventDefault(); if (isShortcutsOpen()) closeShortcuts(); else openShortcuts(); return; }
    if (!mod && !e.altKey && e.key === "/" && !typing) { e.preventDefault(); if (chatInput) chatInput.focus(); return; }
  });

  // API base + model inputs
  if (apiBaseInput) {
    try { const saved = localStorage.getItem(API_KEY); if (saved) apiBaseInput.value = saved; } catch {}
    let t;
    apiBaseInput.addEventListener("input", () => { clearTimeout(t); t = setTimeout(checkHealth, 600); });
    apiBaseInput.addEventListener("change", () => {
      try { localStorage.setItem(API_KEY, apiBaseInput.value.trim()); } catch {}
      if (!apiBaseInput.value.trim()) { discoverBackend().finally(()=>checkHealth()); } else { discoveredBase = ""; checkHealth(); }
    });
  }
  if (modelSelect) {
    try { const savedModel = localStorage.getItem(MODEL_KEY); if (savedModel) modelSelect.value = savedModel; } catch {}
    modelSelect.addEventListener("change", () => {
      try { localStorage.setItem(MODEL_KEY, modelSelect.value || "auto"); } catch {}
      updateHeader();
      showToast(modelSelect.value && modelSelect.value !== "auto" ? "Model selected" : "Auto model selection enabled");
    });
  }
}

function init() {
  syncSidebarForViewport();
  if (emptyGreeting) emptyGreeting.textContent = getGreeting(new Date());
  bindEvents();
  loadState();
  renderSessionList();
  renderMessages();
  updateHeader();
  autoResize();
  discoverBackend().finally(() => checkHealth());
  startHealthPolling();
}

init();
