const appShell = document.getElementById('app-shell');
const chatLog = document.getElementById('chat-log');
const chatCollection = document.getElementById('chat-collection');
const chatEmpty = document.getElementById('chat-empty');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatStatus = document.getElementById('chat-status');
const emptyGreeting = document.getElementById('empty-greeting');
const apiBaseInput = document.getElementById('api-base');
const newChatBtn = document.getElementById('new-chat');
const sidebarToggle = document.getElementById('sidebar-toggle');
const brandHome = document.getElementById('brand-home');

let busy = false;
let workingEl = null;

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showEmpty() {
  chatEmpty.style.display = 'flex';
}

function hideEmpty() {
  chatEmpty.style.display = 'none';
}

function setStatus(state) {
  busy = state === 'thinking';
  chatSend.disabled = busy || !chatInput.value.trim();
  if (busy) {
    chatStatus.textContent = 'Thinking…';
    if (!workingEl) {
      workingEl = document.createElement('div');
      workingEl.className = 'working';
      workingEl.setAttribute('role', 'status');
      workingEl.innerHTML = '<span class="working-dot" aria-hidden="true"></span><span>Jo is thinking…</span>';
      chatCollection.appendChild(workingEl);
      scrollToBottom();
    }
  } else {
    chatStatus.textContent = '';
    if (workingEl) {
      workingEl.remove();
      workingEl = null;
    }
  }
}

function addMessage(role, content, isError) {
  hideEmpty();
  if (workingEl) {
    workingEl.remove();
    workingEl = null;
  }
  const message = document.createElement('article');
  message.className = 'message ' + (role === 'user' ? 'message-user' : 'message-assistant') + (isError ? ' message-error' : '');
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  const body = document.createElement('div');
  body.className = role === 'user' ? 'message-text' : 'message-content message-text';
  body.textContent = content;
  bubble.appendChild(body);
  message.appendChild(bubble);
  chatCollection.appendChild(message);
  scrollToBottom();
}

async function sendToJo(message) {
  const base = (apiBaseInput && apiBaseInput.value ? apiBaseInput.value : 'https://ouroboros-agent.ai').trim().replace(/\/$/, '');
  const response = await fetch(base + '/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error('HTTP ' + response.status);
  }

  const contentType = response.headers.get('content-type') || '';
  let content = await response.text();

  if (contentType.includes('application/json')) {
    const data = JSON.parse(content);
    content = data.response || data.message || data.content || data.reply || (typeof data === 'string' ? data : JSON.stringify(data));
  }

  return content;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || busy) return;

  addMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('thinking');

  try {
    const content = await sendToJo(text);
    addMessage('assistant', content);
  } catch (error) {
    addMessage('assistant', 'Could not reach Jo backend: ' + error.message, true);
  } finally {
    setStatus('idle');
  }
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  await sendMessage();
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
  chatSend.disabled = busy || !chatInput.value.trim();
});

chatInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    if (!busy && chatInput.value.trim()) chatForm.requestSubmit();
  }
});

function clearChat() {
  const nodes = Array.from(chatCollection.children);
  for (const node of nodes) {
    if (node !== chatEmpty) node.remove();
  }
  workingEl = null;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('idle');
  showEmpty();
  chatInput.focus();
}

if (newChatBtn) newChatBtn.addEventListener('click', clearChat);
if (brandHome) brandHome.addEventListener('click', () => chatInput.focus());

if (sidebarToggle) {
  sidebarToggle.addEventListener('click', () => {
    appShell.classList.toggle('sidebar-collapsed');
  });
}

function getGreeting(date) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 18) return 'Good afternoon';
  if (hour >= 18 && hour < 23) return 'Good evening';
  return 'Good night';
}

function init() {
  if (emptyGreeting) emptyGreeting.textContent = getGreeting(new Date());
  chatSend.disabled = true;
  showEmpty();
  if (apiBaseInput) {
    const saved = (() => { try { return localStorage.getItem('jo.apiBase'); } catch { return null; } })();
    if (saved) apiBaseInput.value = saved;
    apiBaseInput.addEventListener('change', () => {
      try { localStorage.setItem('jo.apiBase', apiBaseInput.value.trim()); } catch {}
    });
  }
}

init();
