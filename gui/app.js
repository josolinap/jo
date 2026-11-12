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
const mobileMenu = document.getElementById('mobile-menu');

let busy = false;
let workingEl = null;
let controller = null;
let messages = [];

const STORAGE_KEY = 'jo.chat.v1';
const API_KEY = 'jo.apiBase';

function scrollToBottom(force) {
  if (force) {
    chatLog.scrollTop = chatLog.scrollHeight;
    return;
  }
  const near = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight < 120;
  if (near) chatLog.scrollTop = chatLog.scrollHeight;
}

function showEmpty() { chatEmpty.style.display = 'flex'; }
function hideEmpty() { chatEmpty.style.display = 'none'; }

function saveState() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-100))); } catch {}
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderContent(el, text, role) {
  if (role === 'user') {
    el.textContent = text;
    return;
  }
  const parts = String(text).split(/```/);
  let html = '';
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      let code = parts[i];
      code = code.replace(/^\w*\n/, '');
      html += '<pre><code>' + escapeHtml(code) + '</code></pre>';
    } else {
      let chunk = escapeHtml(parts[i]);
      chunk = chunk.replace(/`([^`\n]+)`/g, '<code>$1</code>');
      chunk = chunk.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
      chunk = chunk.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
      html += chunk;
    }
  }
  el.innerHTML = html;
}

function setStatus(state) {
  busy = state === 'thinking';
  chatSend.disabled = busy || !chatInput.value.trim();
  if (chatStop) chatStop.hidden = !busy;
  chatStatus.textContent = busy ? 'Thinking…' : '';
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

function addMessage(role, content, opts) {
  opts = opts || {};
  hideEmpty();
  if (workingEl) { workingEl.remove(); workingEl = null; }
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
      try {
        await navigator.clipboard.writeText(content);
        copy.textContent = 'Copied';
        setTimeout(() => { copy.textContent = 'Copy'; }, 1200);
      } catch {
        copy.textContent = 'Copy failed';
        setTimeout(() => { copy.textContent = 'Copy'; }, 1200);
      }
    });
    actions.appendChild(copy);
    message.appendChild(actions);
  }
  chatCollection.appendChild(message);
  scrollToBottom(false);
  if (!opts.skipStore) {
    messages.push({ role, content, error: !!opts.error, ts: Date.now() });
    saveState();
  }
}

function getApiBase() {
  const v = (apiBaseInput && apiBaseInput.value ? apiBaseInput.value : 'https://ouroboros-agent.ai').trim().replace(/\/$/, '');
  return v || 'https://ouroboros-agent.ai';
}

async function sendToJo(message, signal) {
  const base = getApiBase();
  const response = await fetch(base + '/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) throw new Error('HTTP ' + response.status);

  const contentType = response.headers.get('content-type') || '';
  let content = await response.text();
  if (contentType.includes('application/json')) {
    try {
      const data = JSON.parse(content);
      content = data.response || data.message || data.content || data.reply || (typeof data === 'string' ? data : JSON.stringify(data));
    } catch {}
  }
  return content || '(empty response)';
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || busy) return;

  addMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('thinking');
  controller = new AbortController();

  try {
    const content = await sendToJo(text, controller.signal);
    addMessage('assistant', content);
  } catch (error) {
    if (error && error.name === 'AbortError') {
      addMessage('assistant', 'Stopped.', { error: true });
    } else {
      addMessage('assistant', 'Could not reach Jo backend: ' + (error && error.message ? error.message : String(error)), { error: true });
    }
  } finally {
    controller = null;
    setStatus('idle');
  }
}

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  await sendMessage();
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
  chatSend.disabled = busy || !chatInput.value.trim();
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!busy && chatInput.value.trim()) chatForm.requestSubmit();
  }
});

if (chatStop) chatStop.addEventListener('click', () => { if (controller) controller.abort(); });

function clearChat() {
  Array.from(chatCollection.children).forEach(n => { if (n !== chatEmpty) n.remove(); });
  workingEl = null;
  messages = [];
  saveState();
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('idle');
  showEmpty();
  chatInput.focus();
}

if (newChatBtn) newChatBtn.addEventListener('click', clearChat);
if (brandHome) brandHome.addEventListener('click', () => chatInput.focus());

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
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(next);
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
  backendStatus.textContent = 'Status: checking…';
  backendStatus.className = 'backend-status';
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 6000);
  try {
    const res = await fetch(base + '/health', { signal: ctrl.signal });
    clearTimeout(t);
    if (res.ok) {
      backendStatus.textContent = 'Status: online';
      backendStatus.className = 'backend-status ok';
    } else {
      backendStatus.textContent = 'Status: HTTP ' + res.status;
      backendStatus.className = 'backend-status err';
    }
  } catch (e) {
    clearTimeout(t);
    backendStatus.textContent = 'Status: unreachable';
    backendStatus.className = 'backend-status err';
  }
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (!Array.isArray(data)) return;
    messages = data.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string');
    if (messages.length) {
      hideEmpty();
      messages.forEach(m => addMessage(m.role, m.content, { error: !!m.error, skipStore: true }));
      scrollToBottom(true);
    }
  } catch {}
}

function init() {
  if (emptyGreeting) emptyGreeting.textContent = getGreeting(new Date());
  if (apiBaseInput) {
    try {
      const saved = localStorage.getItem(API_KEY);
      if (saved) apiBaseInput.value = saved;
    } catch {}
    let healthTimer;
    const schedule = () => { clearTimeout(healthTimer); healthTimer = setTimeout(checkHealth, 500); };
    apiBaseInput.addEventListener('change', () => {
      try { localStorage.setItem(API_KEY, apiBaseInput.value.trim()); } catch {}
      checkHealth();
    });
    apiBaseInput.addEventListener('input', schedule);
  }
  restoreState();
  setStatus('idle');
  if (!messages.length) showEmpty();
  checkHealth();
}

init();
