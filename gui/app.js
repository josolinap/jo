const appShell = document.getElementById('app-shell');
const chatLog = document.getElementById('chat-log');
const chatCollection = document.getElementById('chat-collection');
const chatEmpty = document.getElementById('chat-empty');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatStop = document.getElementById('chat-stop');
const chatStatus = document.getElementById('chat-status');
const emptyGreeting = document.getElementById('empty-greeting');
const apiBaseInput = document.getElementById('api-base');
const newChatBtn = document.getElementById('new-chat');
const sidebarToggle = document.getElementById('sidebar-toggle');
const themeToggle = document.getElementById('theme-toggle');
const brandHome = document.getElementById('brand-home');
const backendStatus = document.getElementById('backend-status');
const backendMeta = document.getElementById('backend-meta');
const mobileMenu = document.getElementById('mobile-menu');
const sessionListEl = document.getElementById('session-list');
const chatTitle = document.getElementById('chat-title');
const chatSubtitle = document.getElementById('chat-subtitle');
const chatRefresh = document.getElementById('chat-refresh');

let busy = false;
let workingEl = null;
let controller = null;
let sessions = [];
let currentSessionId = null;
let healthInfo = null;

const SESSIONS_KEY = 'jo.sessions.v1';
const CURRENT_KEY = 'jo.currentSession.v1';
const API_KEY = 'jo.apiBase';

function uid() { return 'web_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4); }
function now() { return Date.now(); }

function currentSession() { return sessions.find(s => s.id === currentSessionId) || null; }
function getMessages() { const s = currentSession(); return s ? (s.messages || []) : []; }

function scrollToBottom(force) {
  if (!chatLog) return;
  if (force) { chatLog.scrollTop = chatLog.scrollHeight; return; }
  const near = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight < 120;
  if (near) chatLog.scrollTop = chatLog.scrollHeight;
}

function showEmpty() { if (chatEmpty) chatEmpty.style.display = 'flex'; }
function hideEmpty() { if (chatEmpty) chatEmpty.style.display = 'none'; }

function saveState() {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, 50)));
    if (currentSessionId) localStorage.setItem(CURRENT_KEY, currentSessionId);
  } catch {}
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function sanitizeHref(href) {
  try { const u = new URL(href, location.href); if (u.protocol === 'http:' || u.protocol === 'https:' || u.protocol === 'mailto:') return u.href; } catch {}
  return '#';
}
function renderInline(text) {
  let s = escapeHtml(text);
  const codeSpans = [];
  s = s.replace(/`([^`\n]+)`/g, (_, c) => { const i = codeSpans.length; codeSpans.push('<code>' + c + '</code>'); return '\u0000C' + i + '\u0000'; });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => '<a href="' + escapeHtml(sanitizeHref(href)) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
  s = s.replace(/\u0000C(\d+)\u0000/g, (_, i) => codeSpans[Number(i)] || '');
  return s;
}
function renderMarkdown(text) {
  const src = String(text || '').replace(/\r\n/g, '\n');
  const parts = src.split(/```/);
  let html = '';
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      let code = parts[i]; let lang = '';
      const m = code.match(/^([^\n]*)\n/);
      if (m) { lang = (m[1] || '').trim(); code = code.slice(m[0].length); }
      const safe = escapeHtml(code.replace(/\n$/, ''));
      html += '<div class="code-wrap"><button type="button" class="code-copy" data-code-copy>Copy</button><pre><code' + (lang ? ' data-lang="' + escapeHtml(lang) + '"' : '') + '>' + safe + '</code></pre></div>';
      continue;
    }
    const lines = parts[i].split('\n'); let j = 0;
    while (j < lines.length) {
      const line = lines[j];
      if (!line.trim()) { j++; continue; }
      if (/^###\s+/.test(line)) { html += '<h3>' + renderInline(line.replace(/^###\s+/, '')) + '</h3>'; j++; continue; }
      if (/^##\s+/.test(line)) { html += '<h2>' + renderInline(line.replace(/^##\s+/, '')) + '</h2>'; j++; continue; }
      if (/^#\s+/.test(line)) { html += '<h1>' + renderInline(line.replace(/^#\s+/, '')) + '</h1>'; j++; continue; }
      if (/^(-{3,}|\*{3,})$/.test(line.trim())) { html += '<hr>'; j++; continue; }
      if (/^>\s?/.test(line)) { let bq=[]; while(j<lines.length && /^>\s?/.test(lines[j])){bq.push(lines[j].replace(/^>\s?/,''));j++;} html += '<blockquote>'+renderInline(bq.join('\n')).replace(/\n/g,'<br>')+'</blockquote>'; continue; }
      if (/^(\*|-)\s+/.test(line)) { let items=[]; while(j<lines.length && /^(\*|-)\s+/.test(lines[j])){items.push('<li>'+renderInline(lines[j].replace(/^(\*|-)\s+/,''))+'</li>');j++;} html += '<ul>'+items.join('')+'</ul>'; continue; }
      if (/^\d+\.\s+/.test(line)) { let items=[]; while(j<lines.length && /^\d+\.\s+/.test(lines[j])){items.push('<li>'+renderInline(lines[j].replace(/^\d+\.\s+/,''))+'</li>');j++;} html += '<ol>'+items.join('')+'</ol>'; continue; }
      let para=[line]; j++; while(j<lines.length && lines[j].trim() && !/^(#{1,3}\s+|>\s?|(\*|-)\s+|\d+\.\s+|```|(-{3,}|\*{3,})$)/.test(lines[j])){para.push(lines[j]);j++;}
      html += '<p>' + para.map(renderInline).join('<br>') + '</p>';
    }
  }
  return html || '&nbsp;';
}

function renderContent(el, text, role, streaming) {
  if (role === 'user') { el.textContent = text; return; }
  el.innerHTML = renderMarkdown(text);
  if (streaming) el.classList.add('streaming-caret'); else el.classList.remove('streaming-caret');
  el.querySelectorAll('[data-code-copy]').forEach(btn => {
    if (btn._bound) return; btn._bound = true;
    btn.addEventListener('click', async () => {
      const pre = btn.parentElement && btn.parentElement.querySelector('code');
      const code = pre ? pre.textContent : '';
      try { await navigator.clipboard.writeText(code); btn.textContent = 'Copied'; setTimeout(()=>{btn.textContent='Copy';},1200); }
      catch { btn.textContent = 'Failed'; setTimeout(()=>{btn.textContent='Copy';},1200); }
    });
  });
}

function updateHeader() {
  const s = currentSession();
  if (chatTitle) chatTitle.textContent = s ? (s.title || 'Chat') : 'New chat';
  if (chatSubtitle) {
    const base = getApiBase();
    if (healthInfo && healthInfo.status === 'ok') {
      const parts = [];
      if (healthInfo.provider) parts.push(healthInfo.provider);
      if (healthInfo.model) parts.push(healthInfo.model);
      if (healthInfo.local_reachable) parts.push('local');
      if (healthInfo.keys && healthInfo.keys.omniroute) parts.push('omniroute');
      if (!parts.length && healthInfo.configured) parts.push('connected');
      chatSubtitle.textContent = parts.join(' · ') || 'Backend reachable';
    } else if (!base) {
      chatSubtitle.textContent = 'Set Backend → API base URL (or auto-discover)';
    } else {
      chatSubtitle.textContent = 'Backend not connected';
    }
  }
}

function renderSessionList() {
  if (!sessionListEl) return;
  sessionListEl.innerHTML = '';
  const sorted = [...sessions].sort((a,b) => (b.updatedAt||0)-(a.updatedAt||0));
  for (const s of sorted) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
    const title = document.createElement('span');
    title.className = 'session-title';
    title.textContent = s.title || 'New chat';
    const del = document.createElement('span');
    del.className = 'session-del';
    del.title = 'Delete chat';
    del.textContent = '×';
    del.addEventListener('click', (e) => {
      e.stopPropagation();
      sessions = sessions.filter(x => x.id !== s.id);
      if (currentSessionId === s.id) {
        currentSessionId = sessions.length ? sessions[0].id : null;
        if (!currentSessionId) createSession(true);
        else { loadCurrentSession(); }
      }
      saveState();
      renderSessionList();
      updateHeader();
    });
    item.appendChild(title);
    item.appendChild(del);
    item.addEventListener('click', () => { switchSession(s.id); if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches && appShell) appShell.classList.add('sidebar-collapsed'); });
    sessionListEl.appendChild(item);
  }
}

function clearChatView() {
  if (!chatCollection) return;
  Array.from(chatCollection.children).forEach(n => { if (n !== chatEmpty) n.remove(); });
  workingEl = null;
}

function renderMessages() {
  clearChatView();
  const msgs = getMessages();
  if (!msgs.length) { showEmpty(); return; }
  hideEmpty();
  for (const m of msgs) addMessageEl(m.role, m.content, { error: !!m.error, skipStore: true });
  scrollToBottom(true);
}

function setStatus(state) {
  busy = state === 'thinking';
  if (chatSend) chatSend.disabled = busy || !chatInput.value.trim();
  if (chatStop) chatStop.hidden = !busy;
  if (chatStatus) chatStatus.textContent = busy ? 'Thinking…' : '';
  if (busy) {
    if (!workingEl) {
      workingEl = document.createElement('div');
      workingEl.className = 'working';
      workingEl.setAttribute('role', 'status');
      workingEl.innerHTML = '<span class="working-dot" aria-hidden="true"></span><span>Jo is thinking…</span>';
      chatCollection.appendChild(workingEl);
      scrollToBottom(true);
    }
  } else if (workingEl) {
    workingEl.remove();
    workingEl = null;
  }
}

function addMessageEl(role, content, opts) {
  opts = opts || {};
  if (!opts.skipStore) hideEmpty();
  if (workingEl && !opts.skipStore) { workingEl.remove(); workingEl = null; }
  const message = document.createElement('article');
  message.className = 'message ' + (role === 'user' ? 'message-user' : 'message-assistant') + (opts.error ? ' message-error' : '');
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  const body = document.createElement('div');
  body.className = role === 'user' ? 'message-text' : 'message-content message-text';
  renderContent(body, content, role);
  bubble.appendChild(body);
  message.appendChild(bubble);
  if (role !== 'user') {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'msg-action';
    copy.textContent = 'Copy';
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(content); copy.textContent = 'Copied'; setTimeout(()=>{copy.textContent='Copy';},1200); }
      catch { copy.textContent = 'Copy failed'; setTimeout(()=>{copy.textContent='Copy';},1200); }
    });
    actions.appendChild(copy);
    message.appendChild(actions);
  }
  chatCollection.appendChild(message);
  if (!opts.skipStore) scrollToBottom(false);
  return { message, body };
}

function ensureSession() {
  let s = currentSession();
  if (!s) s = createSession(false);
  return s;
}

function pushMessage(role, content, error) {
  const s = ensureSession();
  s.messages = s.messages || [];
  s.messages.push({ role, content, error: !!error, ts: now() });
  if (role === 'user' && (!s.title || s.title === 'New chat')) {
    s.title = content.trim().slice(0, 40) || 'New chat';
  }
  s.updatedAt = now();
  saveState();
  renderSessionList();
  updateHeader();
}

function getApiBase() {
  const v = (apiBaseInput && apiBaseInput.value ? apiBaseInput.value : '').trim().replace(/\/$/, '');
  return v;
}

async function sendToJo(message, signal, onDelta) {
  const base = getApiBase();
  const s = ensureSession();
  const history = (s.messages || []).slice(-20).map(m => ({ role: m.role, content: m.content }));
  // Try streaming first
  try {
    const res = await fetch(base + '/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ message, history, session_id: s.id }),
      signal,
    });
    if (res.ok && res.body && ((res.headers.get('content-type') || '').includes('text/event-stream'))) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let full = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const lines = part.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (!data) continue;
            let evt;
            try { evt = JSON.parse(data); } catch { continue; }
            if (evt.session_id && evt.session_id !== s.id) { const old = s.id; s.id = evt.session_id; if (currentSessionId === old) currentSessionId = s.id; saveState(); }
            if (evt.error) throw new Error(evt.error);
            if (typeof evt.delta === 'string') { full += evt.delta; if (onDelta) onDelta(full); }
            if (evt.done && typeof evt.response === 'string') { full = evt.response; if (onDelta) onDelta(full); }
          }
        }
      }
      return full || '(empty response)';
    }
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
  }

  const response = await fetch(base + '/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, session_id: s.id }),
    signal,
  });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const contentType = response.headers.get('content-type') || '';
  let content = await response.text();
  if (contentType.includes('application/json')) {
    try {
      const data = JSON.parse(content);
      if (data.session_id && data.session_id !== s.id) { const old = s.id; s.id = data.session_id; if (currentSessionId === old) currentSessionId = s.id; saveState(); }
      content = data.response || data.message || data.content || data.reply || (typeof data === 'string' ? data : JSON.stringify(data));
    } catch {}
  }
  return content || '(empty response)';
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || busy) return;
  const base = getApiBase();
  if (!base) {
    ensureSession();
    pushMessage('user', text, false);
    addMessageEl('user', text, { skipStore: true });
    chatInput.value = ''; chatInput.style.height = 'auto';
    const em = 'No backend configured. Set "Backend → API base URL" in the sidebar to your Jo web backend (e.g. your deployed server, or http://127.0.0.1:8000 when testing locally), then try again. Check GET <API_BASE>/health.';
    pushMessage('assistant', em, true);
    addMessageEl('assistant', em, { error: true, skipStore: true });
    checkHealth();
    return;
  }
  ensureSession();
  pushMessage('user', text, false);
  addMessageEl('user', text, { skipStore: true });
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('thinking');
  controller = new AbortController();

  let msgEl = null; let body = null;
  try {
    hideEmpty();
    if (workingEl) { workingEl.remove(); workingEl = null; }
    msgEl = document.createElement('article');
    msgEl.className = 'message message-assistant';
    const bubble = document.createElement('div'); bubble.className = 'message-bubble';
    body = document.createElement('div'); body.className = 'message-content message-text streaming-caret';
    body.textContent = ''; bubble.appendChild(body); msgEl.appendChild(bubble);
    chatCollection.appendChild(msgEl);
    scrollToBottom(true);

    let finalText = '';
    const content = await sendToJo(text, controller.signal, (partial) => {
      finalText = partial;
      renderContent(body, partial, 'assistant', true);
      scrollToBottom(false);
    });
    finalText = content || finalText || '(empty response)';
    renderContent(body, finalText, 'assistant', false);
    const actions = document.createElement('div'); actions.className = 'message-actions';
    const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'msg-action'; copy.textContent = 'Copy';
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(finalText); copy.textContent = 'Copied'; setTimeout(()=>{copy.textContent='Copy';},1200); }
      catch { copy.textContent = 'Copy failed'; setTimeout(()=>{copy.textContent='Copy';},1200); }
    });
    actions.appendChild(copy); msgEl.appendChild(actions);
    pushMessage('assistant', finalText, false);
    msgEl = null;
  } catch (error) {
    if (body) body.classList.remove('streaming-caret');
    if (msgEl && msgEl.parentNode) msgEl.remove();
    if (error && error.name === 'AbortError') {
      pushMessage('assistant', 'Stopped.', true);
      addMessageEl('assistant', 'Stopped.', { error: true, skipStore: true });
    } else {
      let em = 'Could not reach Jo backend: ' + (error && error.message ? error.message : String(error));
      const isNetwork = error && (error.name === 'TypeError' || /NetworkError|Failed to fetch|fetch resource/i.test(String(error && error.message || error)));
      if (isNetwork) {
        const hints = [];
        if (location.protocol === 'https:' && /^http:\/\//i.test(base)) hints.push('page is HTTPS but API base is HTTP (mixed content blocked) — use an HTTPS backend URL or a tunnel');
        if (/^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)(:\d+)?(\/|$)/i.test(base) && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') hints.push('API base points to your local machine, but you are using the hosted GUI — run backend locally and open GUI locally, or deploy the backend and set its public HTTPS URL');
        hints.push('check that the backend is running and reachable at the API base URL');
        hints.push('confirm CORS is allowed and the endpoint is /v1/chat (GET /health should work)');
        em += '\n\nHints:\n- ' + hints.join('\n- ');
      }
      pushMessage('assistant', em, true);
      addMessageEl('assistant', em, { error: true, skipStore: true });
    }
  } finally {
    controller = null;
    setStatus('idle');
  }
}

chatForm.addEventListener('submit', async (e) => { e.preventDefault(); await sendMessage(); });
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
  chatSend.disabled = busy || !chatInput.value.trim();
});
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!busy && chatInput.value.trim()) chatForm.requestSubmit(); }
});
if (chatStop) chatStop.addEventListener('click', () => { if (controller) controller.abort(); });
if (chatRefresh) chatRefresh.addEventListener('click', () => checkHealth());

document.querySelectorAll('.tip-chip[data-prompt]').forEach(btn => {
  btn.addEventListener('click', () => {
    const p = btn.getAttribute('data-prompt') || '';
    if (!p) return;
    chatInput.value = p;
    chatInput.dispatchEvent(new Event('input'));
    chatInput.focus();
  });
});

function createSession(switchTo) {
  const s = { id: uid(), title: 'New chat', messages: [], createdAt: now(), updatedAt: now() };
  sessions.unshift(s);
  if (switchTo !== false) { currentSessionId = s.id; renderMessages(); }
  saveState();
  renderSessionList();
  updateHeader();
  return s;
}

function switchSession(id) {
  currentSessionId = id;
  saveState();
  renderSessionList();
  renderMessages();
  updateHeader();
  if (chatInput) chatInput.focus();
}

function loadCurrentSession() { renderMessages(); }

function clearOrNewChat() {
  // "New chat" should create a fresh session
  createSession(true);
  if (chatInput) { chatInput.value=''; chatInput.style.height='auto'; chatInput.focus(); }
  setStatus('idle');
}

if (newChatBtn) newChatBtn.addEventListener('click', clearOrNewChat);
if (brandHome) brandHome.addEventListener('click', () => { if (chatInput) chatInput.focus(); });

function toggleSidebar() { appShell.classList.toggle('sidebar-collapsed'); }
if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
if (mobileMenu) mobileMenu.addEventListener('click', toggleSidebar);

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#1f1f1f' : '#f5f5f5');
  try { localStorage.setItem('jo.theme', theme); } catch {}
}
if (themeToggle) themeToggle.addEventListener('click', () => {
  setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

function getGreeting(date) {
  const h = date.getHours();
  if (h >= 5 && h < 12) return 'Good morning';
  if (h >= 12 && h < 18) return 'Good afternoon';
  if (h >= 18 && h < 23) return 'Good evening';
  return 'Good night';
}

async function checkHealth() {
  if (!backendStatus) return;
  const base = getApiBase();
  if (!base) {
    healthInfo = null;
    backendStatus.textContent = 'Status: set API base URL or wait for auto-discovery';
    backendStatus.className = 'backend-status err';
    if (backendMeta) backendMeta.textContent = '';
    updateHeader();
    return;
  }
  backendStatus.textContent = 'Status: checking…';
  backendStatus.className = 'backend-status';
  if (backendMeta) backendMeta.textContent = '';
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 7000);
  try {
    const res = await fetch(base + '/health', { signal: ctrl.signal, cache: 'no-store' });
    clearTimeout(t);
    const ct = res.headers.get('content-type') || '';
    let data = null;
    if (ct.includes('application/json')) { try { data = await res.json(); } catch {} }
    if (res.ok) {
      healthInfo = data || { status: 'ok' };
      const configured = !!(healthInfo.configured || (healthInfo.keys && Object.values(healthInfo.keys).some(Boolean)));
      backendStatus.textContent = configured ? 'Status: online' : 'Status: reachable (no model)';
      backendStatus.className = 'backend-status ' + (configured ? 'ok' : '');
      if (backendMeta) {
        const parts = [];
        if (healthInfo.provider) parts.push('provider: ' + healthInfo.provider);
        if (healthInfo.model) parts.push('model: ' + healthInfo.model);
        if (healthInfo.keys) { const k = Object.keys(healthInfo.keys).filter(x => healthInfo.keys[x]); if (k.length) parts.push('keys: ' + k.join(',')); }
        if (healthInfo.local_reachable) parts.push('local: ready');
        backendMeta.textContent = parts.join(' · ');
      }
    } else {
      healthInfo = null;
      backendStatus.textContent = 'Status: HTTP ' + res.status;
      backendStatus.className = 'backend-status err';
    }
  } catch (e) {
    clearTimeout(t);
    healthInfo = null;
    let msg = 'Status: unreachable';
    if (location.protocol === 'https:' && /^http:\/\//i.test(base)) msg = 'Status: blocked (mixed content)';
    else if (/^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i.test(base) && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') msg = 'Status: unreachable (local URL from hosted GUI)';
    backendStatus.textContent = msg;
    backendStatus.className = 'backend-status err';
  }
  updateHeader();
}

function loadState() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (Array.isArray(data)) sessions = data.filter(s => s && s.id && Array.isArray(s.messages));
    }
  } catch { sessions = []; }
  try {
    const cid = localStorage.getItem(CURRENT_KEY);
    if (cid && sessions.some(s => s.id === cid)) currentSessionId = cid;
  } catch {}
  if (!currentSessionId && sessions.length) currentSessionId = sessions[0].id;
  if (!sessions.length) createSession(true);
  // migrate legacy wrong default
  try {
    const saved = localStorage.getItem(API_KEY);
    if (saved && /ouroboros-agent\.ai/i.test(saved)) {
      localStorage.setItem(API_KEY, '');
      if (apiBaseInput) apiBaseInput.value = '';
    }
  } catch {}
}

async function discoverBackend() {
  const current = getApiBase();
  // Only auto-discover if user hasn't explicitly configured a base
  const saved = (() => { try { return localStorage.getItem(API_KEY) || ''; } catch { return ''; } })();
  if (saved) return;
  try {
    const res = await fetch('./backend.json', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const url = (data && (data.apiBase || data.api_base || data.url) || '').toString().trim().replace(/\/$/, '');
    if (url && !getApiBase()) {
      if (apiBaseInput) apiBaseInput.value = url;
      updateHeader();
    }
  } catch {}
}

function init() {
  if (emptyGreeting) emptyGreeting.textContent = getGreeting(new Date());
  if (apiBaseInput) {
    try { const saved = localStorage.getItem(API_KEY); if (saved) apiBaseInput.value = saved; } catch {}
    let healthTimer;
    const schedule = () => { clearTimeout(healthTimer); healthTimer = setTimeout(checkHealth, 500); };
    apiBaseInput.addEventListener('change', () => { try { localStorage.setItem(API_KEY, apiBaseInput.value.trim()); } catch {} checkHealth(); });
    apiBaseInput.addEventListener('input', schedule);
  }
  loadState();
  renderSessionList();
  renderMessages();
  updateHeader();
  setStatus('idle');
  if (!getMessages().length) showEmpty();
  discoverBackend().finally(() => checkHealth());
}

init();
