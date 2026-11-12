const chatLog = document.getElementById('chat-log');
const chatEmpty = document.getElementById('chat-empty');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const emptyGreeting = document.getElementById('empty-greeting');
const apiBaseInput = document.getElementById('api-base');
const newChatBtn = document.getElementById('new-chat');

let busy = false;

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showEmpty() {
  chatEmpty.style.display = 'flex';
}

function addMessage(role, content) {
  const message = document.createElement('div');
  message.className = 'message ' + (role === 'user' ? 'is-user' : 'is-assistant');

  const contentEl = document.createElement('div');
  contentEl.className = 'message-content';

  const text = document.createElement('div');
  text.className = 'message-text';
  text.textContent = content;

  contentEl.appendChild(text);
  message.appendChild(contentEl);
  chatLog.appendChild(message);
  scrollToBottom();
}

function setStatus(state) {
  busy = state === 'thinking';
  statusDot.classList.toggle('busy', busy);
  statusText.textContent = state === 'thinking' ? 'THINKING · SELF-CREATING' : 'ONLINE · SELF-CREATING';
}

async function sendToJo(message) {
  const base = apiBaseInput.value.trim().replace(/\/$/, '');
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
    content = data.response || data.message || data.content || data.reply || JSON.stringify(data);
  }

  return content;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  addMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  setStatus('thinking');

  try {
    const content = await sendToJo(text);
    addMessage('assistant', content);
  } catch (error) {
    addMessage('assistant', '⚠️ Could not reach Jo backend: ' + error.message);
  } finally {
    setStatus('idle');
  }
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!chatInput.value.trim()) return;
  await sendMessage();
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 192) + 'px';
  chatSend.disabled = busy || !chatInput.value.trim();
});

chatInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

chatSend.addEventListener('click', () => {
  chatForm.requestSubmit();
});

newChatBtn.addEventListener('click', () => {
  while (chatLog.firstChild && chatLog.firstChild !== chatEmpty) {
    chatLog.removeChild(chatLog.firstChild);
  }
  chatInput.value = '';
  chatInput.style.height = 'auto';
  chatSend.disabled = true;
  setStatus('idle');
  showEmpty();
});

function getGreeting(date) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 9) return 'Good morning';
  if (hour >= 9 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 14) return 'Good afternoon';
  if (hour >= 14 && hour < 18) return 'Good afternoon';
  if (hour >= 18 && hour < 23) return 'Good evening';
  return 'Good night';
}

function init() {
  setStatus('idle');
  showEmpty();
  emptyGreeting.textContent = getGreeting(new Date());
  chatSend.disabled = true;
}

init();
