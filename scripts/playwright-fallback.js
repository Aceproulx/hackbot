#!/usr/bin/env node
/**
 * playwright-fallback.js — drive the browser when the Playwright MCP tools are
 * unavailable in the agent's toolset (browser_navigate / browser_snapshot /
 * browser_click / browser_type / browser_evaluate missing, or the MCP
 * connection is closed).
 *
 * Wraps the globally-installed `playwright-mcp` binary and speaks MCP
 * JSON-RPC to it over stdio. Same flags as the opencode MCP config.
 *
 * USAGE:
 *   node scripts/playwright-fallback.js navigate <url> [--profile <dir>]
 *   node scripts/playwright-fallback.js snapshot [--profile <dir>]
 *   node scripts/playwright-fallback.js find <text-or-regex> [--profile <dir>]
 *   node scripts/playwright-fallback.js click <ref> [--profile <dir>]
 *   node scripts/playwright-fallback.js type <ref> <text> [--profile <dir>]
 *   node scripts/playwright-fallback.js press <key> [--profile <dir>]
 *   node scripts/playwright-fallback.js hover <ref> [--profile <dir>]
 *   node scripts/playwright-fallback.js evaluate <js> [--profile <dir>]
 *   node scripts/playwright-fallback.js console [--profile <dir>]
 *   node scripts/playwright-fallback.js network [--profile <dir>]
 *   node scripts/playwright-fallback.js screenshot <out.png> [--profile <dir>]
 *   node scripts/playwright-fallback.js wait <seconds> [--profile <dir>]
 *   node scripts/playwright-fallback.js close [--profile <dir>]
 *
 * PROFILE RESOLUTION (in order):
 *   1. --profile <dir> flag
 *   2. $PLAYWRIGHT_MCP_USER_DATA_DIR
 *   3. $AGENT_BROWSER_PROFILE
 *   4. none (ephemeral profile — session does NOT persist)
 *
 * Each invocation spawns a fresh playwright-mcp server, performs ONE action,
 * prints the result, and exits. The browser session persists across
 * invocations ONLY when a profile dir is used (cookies/localStorage are saved
 * into it). Without a profile, each call starts from a clean browser.
 */

const { spawn } = require('child_process');

// ---- config (must match the opencode MCP config) ----
const SERVER_FLAGS = [
  '--no-sandbox',
  '--browser', 'chrome',
  '--caps', 'vision',
  '--console-level', 'info',
  '--ignore-https-errors',
];

// ---- arg parsing ----
const args = process.argv.slice(2);
let profile = null;
const profileIdx = args.indexOf('--profile');
if (profileIdx !== -1) {
  profile = args[profileIdx + 1];
  args.splice(profileIdx, 2);
}
if (!profile) profile = process.env.PLAYWRIGHT_MCP_USER_DATA_DIR || process.env.AGENT_BROWSER_PROFILE || null;

const cmd = args[0];
const rest = args.slice(1);

if (!cmd) {
  console.error('Usage: node playwright-fallback.js <navigate|snapshot|find|click|type|press|hover|evaluate|console|network|screenshot|wait|close> [args] [--profile <dir>]');
  process.exit(2);
}

// ---- MCP client ----
function startServer() {
  const serverArgs = [...SERVER_FLAGS];
  if (profile) serverArgs.push('--user-data-dir', profile);
  const child = spawn('playwright-mcp', serverArgs, { stdio: ['pipe', 'pipe', 'pipe'] });
  let buf = '';
  let stderrBuf = '';
  const pending = new Map();
  let nextId = 1;

  child.stderr.on('data', (d) => {
    stderrBuf += d;
    if (stderrBuf.length > 4000) stderrBuf = stderrBuf.slice(-4000);
  });

  child.stdout.on('data', (d) => {
    buf += d;
    let idx;
    while ((idx = buf.indexOf('\n')) !== -1) {
      const line = buf.slice(0, idx);
      buf = buf.slice(idx + 1);
      if (!line.trim()) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    }
  });

  function send(method, params, id) {
    return new Promise((resolve, reject) => {
      const msgId = id || nextId++;
      pending.set(msgId, { resolve, reject });
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: msgId, method, params }) + '\n');
    });
  }

  function notify(method, params) {
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
  }

  return { child, send, notify, getStderr: () => stderrBuf };
}

async function callTool(server, name, toolArgs) {
  const res = await server.send('tools/call', { name, arguments: toolArgs });
  // MCP tool results: { content: [{ type: 'text', text }], isError? }
  if (res.isError) {
    const errText = (res.content || []).map((c) => c.text || '').join('\n');
    throw new Error('Tool error: ' + errText);
  }
  return (res.content || []).map((c) => c.text || '').join('\n');
}

async function main() {
  const server = startServer();
  const timeout = setTimeout(() => {
    console.error('FATAL: playwright-mcp did not respond in 30s. stderr:\n' + server.getStderr());
    server.child.kill('SIGKILL');
    process.exit(1);
  }, 30000);

  try {
    await server.send('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'playwright-fallback', version: '1.0.0' },
    });
    server.notify('notifications/initialized', {});

    let output;
    switch (cmd) {
      case 'navigate': {
        const url = rest[0];
        if (!url) throw new Error('navigate requires a URL');
        await callTool(server, 'browser_navigate', { url });
        output = await callTool(server, 'browser_snapshot', {});
        break;
      }
      case 'snapshot':
        output = await callTool(server, 'browser_snapshot', {});
        break;
      case 'find': {
        const q = rest[0];
        if (!q) throw new Error('find requires text or /regex/');
        const isRegex = q.startsWith('/') && q.endsWith('/');
        output = await callTool(server, 'browser_find', isRegex ? { regex: q.slice(1, -1) } : { text: q });
        break;
      }
      case 'click': {
        const target = rest[0];
        if (!target) throw new Error('click requires an element ref (from snapshot)');
        output = await callTool(server, 'browser_click', { target });
        break;
      }
      case 'type': {
        const target = rest[0];
        const text = rest.slice(1).join(' ');
        if (!target || !text) throw new Error('type requires <ref> <text>');
        output = await callTool(server, 'browser_type', { target, text });
        break;
      }
      case 'press': {
        const key = rest[0];
        if (!key) throw new Error('press requires a key (e.g. Enter, Tab)');
        output = await callTool(server, 'browser_press_key', { key });
        break;
      }
      case 'hover': {
        const target = rest[0];
        if (!target) throw new Error('hover requires an element ref');
        output = await callTool(server, 'browser_hover', { target });
        break;
      }
      case 'evaluate': {
        const fn = rest.join(' ');
        if (!fn) throw new Error('evaluate requires a JS function body, e.g. "() => document.title"');
        output = await callTool(server, 'browser_evaluate', { function: fn });
        break;
      }
      case 'console':
        output = await callTool(server, 'browser_console_messages', { level: 'info' });
        break;
      case 'network':
        output = await callTool(server, 'browser_network_requests', { static: false });
        break;
      case 'screenshot': {
        const file = rest[0];
        if (!file) throw new Error('screenshot requires an output path');
        await callTool(server, 'browser_take_screenshot', { filename: file, scale: 'css' });
        output = 'Screenshot saved: ' + file;
        break;
      }
      case 'wait': {
        const secs = parseFloat(rest[0]) || 1;
        await callTool(server, 'browser_wait_for', { time: secs });
        output = 'Waited ' + secs + 's';
        break;
      }
      case 'close':
        await callTool(server, 'browser_close', {});
        output = 'Browser closed';
        break;
      default:
        throw new Error('Unknown command: ' + cmd);
    }

    clearTimeout(timeout);
    console.log(output);
  } catch (e) {
    clearTimeout(timeout);
    console.error('ERROR: ' + e.message);
    if (server.getStderr()) console.error('SERVER STDERR:\n' + server.getStderr());
    process.exit(1);
  } finally {
    server.child.kill();
  }
}

main();