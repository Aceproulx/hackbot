const CHECKBOX_SELECTOR = [
  '#recaptcha-anchor',
  '.recaptcha-checkbox',
  '[role="checkbox"]'
].join(',');

const POLL_INTERVAL_MS = 1000;

function isChecked(el) {
  return el.classList.contains('recaptcha-checkbox-checked') ||
         el.getAttribute('aria-checked') === 'true';
}

function fireClick(el) {
  const rect = el.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  const opts = {
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window,
    clientX: x,
    clientY: y
  };
  for (const type of ['pointerover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
    const Ctor = type.startsWith('pointer') ? PointerEvent : MouseEvent;
    el.dispatchEvent(new Ctor(type, opts));
  }
}

function reportStatus(state, meta) {
  chrome.runtime.sendMessage({
    captchaStatus: { state, meta: { ...(meta || {}), frameUrl: location.href, path: location.pathname } },
  }).catch(() => {});
}

let reportedSolving = false;
let reportedSolved = false;
let clickRequested = false;
let mySessionId = null;
let pollTimer = null;

// Returns 'checked' if already checked, 'clicked' if it clicked,
// 'notfound' if no checkbox in this frame, 'waiting' if checkbox present but no command.
function maybeClick() {
  const el = document.querySelector(CHECKBOX_SELECTOR);
  if (!el) return 'notfound';

  if (isChecked(el)) {
    if (!reportedSolved) {
      reportedSolved = true;
      reportStatus('solved');
    }
    return 'checked';
  }

  if (reportedSolved) {
    reportedSolved = false;
    reportStatus('failed', { reason: 'checkbox reset after being checked' });
  }

  if (clickRequested && !el.hasAttribute('data-nar-clicked')) {
    el.setAttribute('data-nar-clicked', '1');
    setTimeout(() => fireClick(el), 300);
    return 'clicked';
  }

  return 'waiting';
}

let pollTicks = 0;

async function pollForClick() {
  pollTicks++;
  if (!mySessionId) {
    // Report once so we can see from the relay if the session-id handshake failed.
    if (pollTicks === 10) reportStatus('idle', { pollNoSession: true });
    return;
  }

  // The content script CANNOT fetch the relay directly (CORS-blocked inside the
  // google.com frame), so the background does the fetch and responds here.
  let sessions = [];
  try {
    const resp = await chrome.runtime.sendMessage({ fetchPending: true });
    sessions = (resp && resp.sessions) || [];
  } catch (e) {
    return; // background unavailable
  }

  if (!sessions.includes(mySessionId)) return;

  // This session has a pending MCP click command — allow clicking now
  clickRequested = true;
  const result = maybeClick();
  reportStatus('idle', { pollHit: true, result, mySessionId, pending: sessions, frameId: location.pathname });
  if (result === 'clicked' || result === 'checked') {
    chrome.runtime.sendMessage({ clickAck: true, session: mySessionId }).catch(() => {});
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(pollForClick, POLL_INTERVAL_MS);
}

async function initSessionId() {
  try {
    const resp = await chrome.runtime.sendMessage({ getSessionId: true });
    if (resp && resp.sessionId) {
      mySessionId = resp.sessionId;
      reportStatus('idle', { sessionIdReceived: mySessionId });
      startPolling();
    } else {
      reportStatus('idle', { sessionIdFailed: true });
    }
  } catch (e) {
    reportStatus('idle', { sessionIdError: String(e && e.message || e) });
  }
}

// The challenge iframe (image/audio puzzle, solved by Buster) lives at a
// /bframe path. Its appearance means the simple click wasn't enough and a
// harder challenge is now in progress.
if (!reportedSolving && /\/recaptcha\/(api2|enterprise)\/bframe/.test(location.pathname)) {
  reportedSolving = true;
  reportStatus('solving');
}

// Push path: background broadcasts a click command to all frames.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.action === 'click_captcha') {
    clickRequested = true;
    maybeClick();
    sendResponse({ ok: true });
  }
  return false;
});

// Report initial status — do NOT auto-click
reportStatus('idle', { hasCheckbox: !!document.querySelector(CHECKBOX_SELECTOR) });

// Watch for the checkbox appearing (reCAPTCHA can inject it late).
// Clicking only happens when clickRequested is true (set by the MCP command).
const root = document.body || document.documentElement;
if (root) {
  new MutationObserver(maybeClick).observe(root, { childList: true, subtree: true });
}

// Ask for session ID and start the background-mediated polling loop
initSessionId();