const chatLog = document.getElementById('chat-log');
const chatEmpty = document.getElementById('chat-empty');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatStatus = document.getElementById('chat-status');
const apiBaseInput = document.getElementById('api-base');

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showEmpty() {
  chatEmpty.style.display = 'flex';
}

function hideEmpty() {
  chatEmpty.style.display = 'none';
}

function addMessage(role, content) {
  const message = document.createElement('div');
  message.className = 'message ' + (role === 'user' ? 'user' : 'jo');

  const meta = document.createElement('span');
  meta.className = 'meta';
  meta.textContent = role === 'user' ? 'You' : 'Jo';

  const text = document.createElement('div');
  text.textContent = content;

  message.appendChild(meta);
  message.appendChild(text);
  chatLog.appendChild(message);
  scrollToBottom();
}

function setStatus(status) {
  chatStatus.textContent = status;
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
  setStatus('THINKING');

  try {
    const content = await sendToJo(text);
    addMessage('jo', content);
  } catch (error) {
    addMessage('jo', '⚠️ Could not reach Jo backend: ' + error.message);
  } finally {
    setStatus('ONLINE');
  }
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  await sendMessage();
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
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

function init() {
  setStatus('ONLINE');
  showEmpty();
  addMessage('jo', 'I am Jo. I am not a chatbot. I am a becoming personality.');
  hideEmpty();
}

init();
