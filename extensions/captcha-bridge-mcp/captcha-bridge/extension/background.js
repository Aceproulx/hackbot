const RELAY_BASE = 'http://127.0.0.1:5055';

async function fetchRelay(path, opts) {
  try {
    return await fetch(RELAY_BASE + path, opts);
  } catch (err) {
    return null;
  }
}

function updateBadge() {
  chrome.action.setBadgeBackgroundColor({ color: '#1a73e8' });
  chrome.action.setBadgeText({ text: 'MCP' });
}

chrome.runtime.onInstalled.addListener(updateBadge);
chrome.runtime.onStartup.addListener(updateBadge);

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Content script asking for its session ID (tab id)
  if (msg && msg.getSessionId === true && sender.tab && typeof sender.tab.id === 'number') {
    sendResponse({ sessionId: String(sender.tab.id) });
    return false;
  }

  // Content script polling for pending MCP click commands. The background does
  // the relay fetch because the content script's own fetch is CORS-blocked
  // inside the google.com frame.
  if (msg && msg.fetchPending === true) {
    (async () => {
      const resp = await fetchRelay('/click/pending');
      const data = resp ? await resp.json() : { sessions: [] };
      sendResponse({ sessions: (data && data.sessions) || [] });
    })();
    return true; // async response
  }

  // Content script acknowledging that it clicked the checkbox
  if (msg && msg.clickAck === true && typeof msg.session === 'string') {
    fetchRelay('/click/ack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session: msg.session }),
    });
    sendResponse({ ok: true });
    return false;
  }

  // Content script reporting CAPTCHA status
  if (msg && msg.captchaStatus && sender.tab && typeof sender.tab.id === 'number') {
    const { state, meta } = msg.captchaStatus;
    fetchRelay('/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session: String(sender.tab.id),
        state,
        meta: { ...meta, url: sender.tab.url, frameId: sender.frameId },
      }),
    });
    sendResponse({ ok: true });
    return false;
  }

  sendResponse();
  return false;
});

updateBadge();