#!/usr/bin/env node
/**
 * pw-drive.js — minimal reliable Playwright MCP driver for hackbot.
 * Builds the MCP config inline (same settings as playwright-mcp.sh: Caido
 * proxy, buster + captcha-bridge extensions, persistent profile dir), spawns
 * @playwright/mcp, performs ONE action, prints result, exits.
 *
 * Usage:
 *   node pw-drive.js navigate <url> [--profile <dir>]
 *   node pw-drive.js snapshot [--profile <dir>]
 *   node pw-drive.js click <ref>
 *   node pw-drive.js type <ref> <text>
 *   node pw-drive.js press <key>
 *   node pw-drive.js find <text>
 *   node pw-drive.js evaluate <js>
 *   node pw-drive.js screenshot <out.png>
 *   node pw-drive.js wait <seconds>
 *   node pw-drive.js close-tabs
 *
 * Profile resolution: --profile flag > $PLAYWRIGHT_MCP_USER_DATA_DIR >
 * $AGENT_BROWSER_PROFILE. Without a profile the session does not persist.
 */
const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');
const path = require('path');

const REPO = '/home/aceos/Projects/hackbot';
const PROXY = 'http://127.0.0.1:8080';
const EXTENSIONS = [
  '/home/aceos/Projects/hackbot/extensions/buster/buster',
  '/home/aceos/Projects/hackbot/extensions/captcha-bridge-mcp/captcha-bridge/extension',
].filter(d => fs.existsSync(d)).join(',');

const args = process.argv.slice(2);
let profile = null;
const pIdx = args.indexOf('--profile');
if (pIdx !== -1) { profile = args[pIdx + 1]; args.splice(pIdx, 2); }
if (!profile) profile = process.env.PLAYWRIGHT_MCP_USER_DATA_DIR || process.env.AGENT_BROWSER_PROFILE || null;

const cmd = args[0];
const rest = args.slice(1);
if (!cmd) { console.error('usage: pw-drive.js <navigate|snapshot|click|type|press|find|evaluate|screenshot|wait|close-tabs> [args] [--profile <dir>]'); process.exit(2); }

// ---- config ----
const baseArgs = ['--no-sandbox', '--proxy-server=' + PROXY];
if (EXTENSIONS) {
  baseArgs.push('--load-extension=' + EXTENSIONS, '--disable-extensions-except=' + EXTENSIONS);
}
const browser = {
  browserName: 'chromium',
  launchOptions: {
    channel: 'chromium',
    headless: true,
    ignoreDefaultArgs: ['--disable-extensions'],
    args: baseArgs,
  },
};
if (profile) browser.userDataDir = profile;
const configPath = path.join(os.tmpdir(), 'pw-drive-' + process.pid + '.json');
fs.writeFileSync(configPath, JSON.stringify({ browser }));

// ---- spawn ----
const child = spawn('npx', ['-y', '@playwright/mcp@latest', '--config', configPath, '--caps', 'vision', '--console-level', 'info', '--ignore-https-errors'], {
  stdio: ['pipe', 'pipe', 'pipe'],
  detached: true,
});
function killTree() { try { process.kill(-child.pid, 'SIGKILL'); } catch {} try { child.kill('SIGKILL'); } catch {} }
let buf = '';
let stderrBuf = '';
const pending = new Map();
let nextId = 1;
let init = 0;

child.stderr.on('data', d => { stderrBuf += d; if (stderrBuf.length > 6000) stderrBuf = stderrBuf.slice(-6000); });
child.stdout.on('data', d => {
  buf += d;
  let idx;
  while ((idx = buf.indexOf('\n')) !== -1) {
    const line = buf.slice(0, idx); buf = buf.slice(idx + 1);
    if (!line.trim()) continue;
    let msg; try { msg = JSON.parse(line); } catch { continue; }
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

const timeout = setTimeout(() => {
  console.error('FATAL: no response in 160s. stderr:\n' + stderrBuf);
  killTree();
  try { fs.unlinkSync(configPath); } catch {}
  process.exit(1);
}, 160000);

async function main() {
  await send('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'pw-drive', version: '1.0.0' } });
  init = 1;
  // notifications/new-notifications aren't required; send initialized
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} }) + '\n');

  let toolArgs = {};
  let toolName = cmd;
  if (cmd === 'script') {
    const steps = JSON.parse(fs.readFileSync(rest[0], 'utf8'));
    const results = [];
    for (const st of steps) {
      const tn = st.tool || st.name;
      const ta = st.args || st.params || {};
      try {
        const r = await send('tools/call', { name: tn, arguments: ta });
        const txt = (r.content || []).map(c => (c.type === 'text' ? c.text : c.type === 'image' ? '[image]' : JSON.stringify(c))).join('\n');
        results.push({ tool: tn, ok: !r.isError, text: txt.slice(0, st.cap || 4000) });
      } catch (e) {
        results.push({ tool: tn, ok: false, error: e.message });
      }
    }
    console.log(JSON.stringify(results, null, 2));
    clearTimeout(timeout);
    try { child.stdin.end(); } catch {}
    setTimeout(() => { try { child.kill('SIGKILL'); } catch {} try { fs.unlinkSync(configPath); } catch {} process.exit(0); }, 500);
    return;
  }
  switch (cmd) {
    case 'navigate': toolName = 'browser_navigate'; toolArgs = { url: rest[0] }; break;
    case 'snapshot': toolName = 'browser_snapshot'; break;
    case 'click': toolName = 'browser_click'; toolArgs = { target: rest[0] }; break;
    case 'type': toolName = 'browser_type'; toolArgs = { target: rest[0], text: rest[1] }; break;
    case 'press': toolName = 'browser_press_key'; toolArgs = { key: rest[0] }; break;
    case 'find': toolName = 'browser_find'; toolArgs = { text: rest[0] }; break;
    case 'evaluate': toolName = 'browser_evaluate'; toolArgs = { function: rest[0] }; break;
    case 'screenshot': toolName = 'browser_take_screenshot'; toolArgs = { path: rest[0] || '/home/aceos/Projects/hackbot/.playwright-mcp/shot.png' }; break;
    case 'wait': toolName = 'browser_wait_for'; toolArgs = { time: parseInt(rest[0], 10) || 2 }; break;
    case 'close-tabs': toolName = 'browser_close'; break;
    case 'tab-list': toolName = 'browser_tab_list'; break;
    default: throw new Error('unknown command ' + cmd);
  }

  const res = await send('tools/call', { name: toolName, arguments: toolArgs });
  const text = (res.content || []).map(c => (c.type === 'text' ? c.text : c.type === 'image' ? '[image]' : JSON.stringify(c))).join('\n');
  console.log(text);
  if (res.isError) console.error('[tool error]');
}

main().then(() => {
  clearTimeout(timeout);
  try { child.stdin.end(); } catch {}
  setTimeout(() => { killTree(); try { fs.unlinkSync(configPath); } catch {} process.exit(0); }, 500);
}).catch(e => {
  clearTimeout(timeout);
  console.error('ERROR: ' + e.message);
  if (stderrBuf) console.error('stderr:\n' + stderrBuf.slice(-2000));
  killTree();
  try { fs.unlinkSync(configPath); } catch {}
  process.exit(1);
});
child.on('exit', () => { try { fs.unlinkSync(configPath); } catch {} setTimeout(() => process.exit(0), 100); });