#!/usr/bin/env node
/**
 * pw-flow.js — multi-action Playwright MCP driver (fixed param names per
 * playwright-fallback.js: navigate {url}, click/type {target}, etc.)
 * Starts ONE playwright-mcp server (profile from env), executes a sequence of
 * named actions against the SAME persistent tab.
 *
 * Usage:
 *   node pw-flow.js '[
 *     {"a":"navigate","url":"https://..."},
 *     {"a":"wait","ms":6000},
 *     {"a":"snapshot"},
 *     {"a":"click","target":"e12"},
 *     {"a":"type","target":"e12","text":"foo"},
 *     {"a":"evaluate","js":"() => document.body.innerText.slice(0,2000)"},
 *     {"a":"network"},
 *     {"a":"close"}
 *   ]'
 */
const { spawn } = require('child_process');
const path = require('path');

const SCHEMA = path.join(__dirname, 'playwright-mcp.sh');
const profile = process.env.PLAYWRIGHT_MCP_USER_DATA_DIR || process.env.AGENT_BROWSER_PROFILE || null;

const argv = process.argv.slice(2);
let flow;
try {
  flow = JSON.parse(argv.join(' ').trim());
} catch (e) {
  console.error('Flow JSON parse error:', e.message);
  process.exit(2);
}

function startServer() {
  const serverArgs = [];
  if (profile) serverArgs.push('--profile', profile);
  serverArgs.push('--caps', 'vision', '--console-level', 'info', '--ignore-https-errors');
  const child = spawn('bash', [SCHEMA, ...serverArgs], { stdio: ['pipe', 'pipe', 'pipe'] });
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
  const send = (method, params) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
  const notify = (method, params) => {
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
  };
  return { child, send, notify, getStderr: () => stderrBuf };
}

function textOf(result) {
  if (!result || !result.content) return JSON.stringify(result);
  return result.content.map((c) => c.text || '').join('\n');
}

async function callTool(server, name, toolArgs) {
  const res = await server.send('tools/call', { name, arguments: toolArgs });
  if (res && res.isError) {
    const errText = (res.content || []).map((c) => c.text || '').join('\n');
    throw new Error('Tool error: ' + errText);
  }
  return textOf(res);
}

async function main() {
  const server = startServer();
  const hardTimeout = setTimeout(() => {
    console.error('FATAL: flow exceeded 300s. stderr:\n' + server.getStderr().slice(-1500));
    server.child.kill('SIGKILL');
    process.exit(1);
  }, 300000);
  try {
    await server.send('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'pw-flow', version: '1.0.0' } });
    server.notify('notifications/initialized', {});
    for (const step of flow) {
      const a = step.a || step.action;
      const out = { action: a };
      try {
        switch (a) {
          case 'navigate':
            out.result = (await callTool(server, 'browser_navigate', { url: step.url })).slice(0, 6000);
            break;
          case 'snapshot':
            out.result = (await callTool(server, 'browser_snapshot', {})).slice(0, 16000);
            break;
          case 'find':
            out.result = (await callTool(server, 'browser_find', { text: step.text })).slice(0, 4000);
            break;
          case 'click':
            out.result = (await callTool(server, 'browser_click', { target: step.target, element: step.element })).slice(0, 3000);
            break;
          case 'type':
            out.result = (await callTool(server, 'browser_type', { target: step.target, element: step.element, text: step.text })).slice(0, 3000);
            break;
          case 'select':
            out.result = (await callTool(server, 'browser_select_option', { target: step.target, values: step.values || [step.value] })).slice(0, 3000);
            break;
          case 'press':
            out.result = (await callTool(server, 'browser_press_key', { key: step.key })).slice(0, 1000);
            break;
          case 'hover':
            out.result = (await callTool(server, 'browser_hover', { target: step.target })).slice(0, 1000);
            break;
          case 'wait':
            await new Promise((r) => setTimeout(r, step.ms || 3000));
            out.result = 'waited';
            break;
          case 'evaluate':
            out.result = (await callTool(server, 'browser_evaluate', { function: step.js })).slice(0, 6000);
            break;
          case 'console':
            out.result = (await callTool(server, 'browser_console_messages', { level: 'info' })).slice(0, 4000);
            break;
          case 'network':
            out.result = (await callTool(server, 'browser_network_requests', { static: false })).slice(0, 8000);
            break;
          case 'screenshot':
            await callTool(server, 'browser_take_screenshot', { filename: step.path, scale: 'css' });
            out.result = 'saved ' + step.path;
            break;
          case 'tabs':
            out.result = (await callTool(server, 'browser_tabs', { action: 'list' })).slice(0, 2000);
            break;
          case 'close':
            await callTool(server, 'browser_close', {});
            out.result = 'closed';
            break;
          default:
            out.error = 'unknown action ' + a;
        }
      } catch (e) {
        out.error = e.message.slice(0, 1000);
      }
      console.log('### STEP', JSON.stringify(out));
    }
  } finally {
    clearTimeout(hardTimeout);
    try { await callTool(server, 'browser_close', {}); } catch {}
    await new Promise((r) => setTimeout(r, 500));
    server.child.kill('SIGTERM');
  }
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });