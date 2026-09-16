#!/usr/bin/env node
/**
 * captcha-bridge MCP server.
 *
 * One process, two sides:
 *   - HTTP listener on 127.0.0.1:5055 — the browser extension POSTs
 *     status changes here (idle -> solving -> solved -> expired/failed).
 *   - MCP server over stdio — exposes tools your agent calls directly,
 *     replacing the old CLI:
 *       click_captcha(session?)          — trigger the checkbox click (MCP-only, no auto-click)
 *       get_captcha_status(session?)
 *       wait_for_captcha(session?, timeoutSeconds?, pollIntervalMs?)
 *       reset_captcha_session(session)
 *
 * When the 2-minute solve window expires, status returns action=refresh_page
 * telling the agent to reload the page, re-trigger the form, and reset the session.
 *
 * Run it the same way you'd run any other local MCP server (stdio),
 * e.g. registered in your agent's MCP config pointing at:
 *   node mcp-server/server.js
 */

const express = require('express');
const { McpServer } = require('@modelcontextprotocol/sdk/server/mcp.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { z } = require('zod');

const HTTP_PORT = process.env.CAPTCHA_RELAY_PORT || 5055;
const SOLVE_TTL_MS = 120_000; // 2 minutes, matches the CAPTCHA's real validity window

// ---------------------------------------------------------------------
// Shared state + logic (same as the old relay-server/server.js)
// ---------------------------------------------------------------------

// session -> { state, solvedAt, updatedAt, meta }
const sessions = new Map();
let lastSessionId = null;

// Sessions with a pending MCP-triggered click (Set of session ids)
const pendingClicks = new Set();

function computeView(session) {
  if (!session) {
    return { state: 'idle', solvedAt: null, expiresAt: null, remainingMs: 0, expired: false };
  }

  const view = {
    state: session.state,
    solvedAt: session.solvedAt,
    updatedAt: session.updatedAt,
    meta: session.meta || null,
    expiresAt: null,
    remainingMs: 0,
    expired: false,
  };

  if (session.state === 'solved' && session.solvedAt) {
    const expiresAt = session.solvedAt + SOLVE_TTL_MS;
    const remainingMs = expiresAt - Date.now();
    view.expiresAt = expiresAt;
    view.remainingMs = Math.max(0, remainingMs);
    view.expired = remainingMs <= 0;
    if (view.expired) {
      session.state = 'expired';
      view.state = 'expired';
      view.action = 'refresh_page';
      view.message = 'CAPTCHA solve has expired. Reload the page, re-trigger the form, and call reset_captcha_session before the new solve.';
    }
  }

  return view;
}

function getStatus(session) {
  if (session) {
    return { session, ...computeView(sessions.get(session)) };
  }
  if (!lastSessionId) {
    return { session: null, ...computeView(null) };
  }
  return { session: lastSessionId, ...computeView(sessions.get(lastSessionId)) };
}

function resetSession(session) {
  sessions.delete(session);
  return { ok: true };
}

function recordStatus(session, state, meta) {
  const now = Date.now();
  const existing = sessions.get(session) || {};
  const updated = {
    state,
    solvedAt: state === 'solved' ? now : (state === 'solving' ? null : existing.solvedAt || null),
    updatedAt: now,
    meta: meta || existing.meta || null,
  };
  sessions.set(session, updated);
  lastSessionId = session;
  // A solve, expiry, or failure means the click command has been fulfilled
  if (state === 'solved' || state === 'failed') pendingClicks.delete(session);
  console.error(`[captcha-bridge] session=${session} -> ${state}`); // stderr: keep stdout clean for MCP
  return computeView(updated);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------
// HTTP side — extension talks here
// ---------------------------------------------------------------------

const app = express();
app.use(express.json());

app.get('/status', (req, res) => {
  const session = req.query.session || null;
  const status = getStatus(session);
  res.json(status);
});

app.post('/status', (req, res) => {
  const { session, state, meta } = req.body || {};
  if (!session || typeof session !== 'string') {
    return res.status(400).json({ error: 'session (string) is required' });
  }
  const validStates = ['idle', 'solving', 'solved', 'failed'];
  if (!validStates.includes(state)) {
    return res.status(400).json({ error: `state must be one of ${validStates.join(', ')}` });
  }
  const view = recordStatus(session, state, meta);
  res.json({ ok: true, session, view });
});

// Click command endpoints (extension polls these)
app.get('/click/pending', (_req, res) => {
  res.json({ sessions: [...pendingClicks] });
});

app.post('/click/ack', (req, res) => {
  const { session } = req.body || {};
  if (session) pendingClicks.delete(session);
  res.json({ ok: true });
});

app.listen(HTTP_PORT, '127.0.0.1', () => {
  console.error(`[captcha-bridge] HTTP listener on http://127.0.0.1:${HTTP_PORT} (extension side)`);
});

// ---------------------------------------------------------------------
// MCP side — agent talks here (stdio)
// ---------------------------------------------------------------------

const mcp = new McpServer({ name: 'captcha-bridge', version: '1.0.0' });

mcp.registerTool(
  'get_captcha_status',
  {
    title: 'Get CAPTCHA status',
    description:
      'One-shot check of the CAPTCHA-solving extension\'s current state for a browser tab/session. ' +
      'Returns state (idle/solving/solved/expired/failed), and when solved, expiresAt/remainingMs/expired ' +
      'computed against the real 2-minute solve validity window.',
    inputSchema: {
      session: z.string().optional().describe(
        'Tab/session id to check (e.g. the browser tab ID). Omit to get the most recently updated session.'
      ),
    },
  },
  async ({ session }) => {
    const status = getStatus(session || null);
    return { content: [{ type: 'text', text: JSON.stringify(status, null, 2) }] };
  }
);

mcp.registerTool(
  'wait_for_captcha',
  {
    title: 'Wait for CAPTCHA to be solved',
    description:
      'Polls until the CAPTCHA is solved (and still within its 2-minute window) or reported failed/expired, ' +
      'or until timeoutSeconds elapses. When the solve expires, returns an error with action=refresh_page ' +
      'telling the agent to reload the page. Use this right before you need to submit a form that depends on ' +
      'the solved CAPTCHA, so you know you have a valid window to work with.',
    inputSchema: {
      session: z.string().optional().describe('Tab/session id to wait on. Omit for the most recently updated session.'),
      timeoutSeconds: z.number().positive().default(60).describe('Max seconds to wait before giving up.'),
      pollIntervalMs: z.number().positive().default(500).describe('Milliseconds between polls.'),
    },
  },
  async ({ session, timeoutSeconds, pollIntervalMs }) => {
    const deadline = Date.now() + timeoutSeconds * 1000;
    while (Date.now() < deadline) {
      const status = getStatus(session || null);
      if (status.state === 'solved' && !status.expired) {
        return { content: [{ type: 'text', text: JSON.stringify(status, null, 2) }] };
      }
      if (status.expired) {
        return {
          content: [{ type: 'text', text: JSON.stringify(status, null, 2) }],
          isError: true,
        };
      }
      if (status.state === 'failed') {
        return {
          content: [{ type: 'text', text: JSON.stringify(status, null, 2) }],
          isError: true,
        };
      }
      await sleep(pollIntervalMs);
    }
    return {
      content: [{ type: 'text', text: JSON.stringify({ error: 'timeout', session: session || null, message: 'Timed out waiting for CAPTCHA solve. Reload the page and try again.' }, null, 2) }],
      isError: true,
    };
  }
);

mcp.registerTool(
  'reset_captcha_session',
  {
    title: 'Reset CAPTCHA session',
    description:
      'Clears stored state for a session. Call this right after triggering a page reload (e.g. because the ' +
      '2-minute window expired mid-form), so a stale solved/expired entry isn\'t read back before the new solve lands.',
    inputSchema: {
      session: z.string().describe('Tab/session id to reset.'),
    },
  },
  async ({ session }) => {
    const result = resetSession(session);
    pendingClicks.delete(session);
    return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
  }
);

mcp.registerTool(
  'click_captcha',
  {
    title: 'Click the CAPTCHA checkbox',
    description:
      'Sends a click command to the reCAPTCHA checkbox for the given browser tab/session. ' +
      'The extension will click the checkbox on the next poll cycle (~500ms). ' +
      'Use get_captcha_status or wait_for_captcha afterwards to confirm the solve. ' +
      'This is the ONLY way to trigger a CAPTCHA solve — the extension does not auto-click.',
    inputSchema: {
      session: z.string().optional().describe(
        'Tab/session id to click on (e.g. the browser tab ID). Omit to target the most recently active session.'
      ),
    },
  },
  async ({ session }) => {
    const target = session || lastSessionId;
    if (!target) {
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: 'no active session', message: 'No CAPTCHA session available. Navigate to a page with a reCAPTCHA first.' }, null, 2) }],
        isError: true,
      };
    }
    pendingClicks.add(target);
    console.error(`[captcha-bridge] click requested for session=${target}`);
    return {
      content: [{ type: 'text', text: JSON.stringify({ ok: true, session: target, message: 'Click command queued. The extension will click the checkbox within ~500ms.' }, null, 2) }],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await mcp.connect(transport);
  console.error('[captcha-bridge] MCP server connected on stdio (agent side)');
}

main().catch((err) => {
  console.error('[captcha-bridge] fatal:', err);
  process.exit(1);
});
