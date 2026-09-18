#!/usr/bin/env node
// Fast Playwright MCP driver — uses the cached binary directly (bypasses npx hang).
// Usage: node pw-fast.js <command> [args...]
// Commands: navigate <url>, snapshot, find <text>, click <ref>, type <ref> <text>,
//           press <key>, hover <ref>, evaluate <fn>, console, network, screenshot <path>, wait <secs>, close
const { spawn } = require('child_process');
const path = require('path');
const BIN = process.env.PLAYWRIGHT_MCP_BIN || '/home/aceos/.npm/_npx/9833c18b2d85bc59/node_modules/.bin/playwright-mcp';
const PROFILE = process.env.PLAYWRIGHT_MCP_USER_DATA_DIR || process.env.AGENT_BROWSER_PROFILE || null;

const args = process.argv.slice(2);
const cmd = args[0];
const rest = args.slice(1);

// Build config: same as playwright-mcp.sh but with direct binary
const fs = require('fs');
const os = require('os');
const EXT = '/home/aceos/Projects/hackbot/extensions/buster/buster,/home/aceos/Projects/hackbot/extensions/captcha-bridge-mcp/captcha-bridge/extension';
const browserArgs = ['--no-sandbox', '--proxy-server=http://127.0.0.1:8080', '--load-extension='+EXT, '--disable-extensions-except='+EXT];
const browser = { browserName:'chromium', launchOptions:{ channel:'chromium', headless:true, ignoreDefaultArgs:['--disable-extensions'], args:browserArgs } };
if (PROFILE) browser.userDataDir = PROFILE;
const cfgPath = '/tmp/pw-fast-config.json';
fs.writeFileSync(cfgPath, JSON.stringify({browser}));

const child = spawn('node', [BIN, '--config', cfgPath, '--caps', 'vision'], { stdio:['pipe','pipe','pipe'] });
let buf='', ebuf='';
child.stderr.on('data', d=>ebuf+=d);
let nextId=0; const pending=new Map();
child.stdout.on('data', d=>{
  buf += d;
  const lines = buf.split('\n'); buf = lines.pop();
  for(const line of lines){ if(!line.trim()) continue; try{ const m=JSON.parse(line); if(m.id && pending.has(m.id)){ pending.get(m.id)(m); pending.delete(m.id);} }catch(e){} }
});
function send(m,p){ return new Promise(res=>{ const i=++nextId; pending.set(i,res); child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:i,method:m,params:p})+'\n'); }); }
(async()=>{
  await send('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'pw-fast',version:'1.0'}});
  child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized',params:{}})+'\n');
  async function call(name, toolArgs){ const r = await send('tools/call',{name, arguments:toolArgs}); return (r.result?.content||[]).map(c=>c.text||'').join('\n'); }
  let out = '';
  switch(cmd){
    case 'navigate': out = await call('browser_navigate',{url:rest[0]}); out += '\n---SNAPSHOT---\n' + await call('browser_snapshot',{}); break;
    case 'snapshot': out = await call('browser_snapshot',{}); break;
    case 'find': out = await call('browser_find', rest[0].startsWith('/')&&rest[0].endsWith('/') ? {regex:rest[0].slice(1,-1)} : {text:rest[0]}); break;
    case 'click': out = await call('browser_click',{target:rest[0]}); break;
    case 'type': out = await call('browser_type',{target:rest[0], text:rest.slice(1).join(' ')}); break;
    case 'press': out = await call('browser_press_key',{key:rest[0]}); break;
    case 'hover': out = await call('browser_hover',{target:rest[0]}); break;
    case 'evaluate': out = await call('browser_evaluate',{function:rest.join(' ')}); break;
    case 'console': out = await call('browser_console_messages',{level:'info'}); break;
    case 'network': out = await call('browser_network_requests',{static:false}); break;
    case 'screenshot': out = await call('browser_take_screenshot',{filename:rest[0], scale:'css'}); break;
    case 'wait': out = await call('browser_wait_for',{time:parseFloat(rest[0])||1}); break;
    case 'close': out = await call('browser_close',{}); break;
    default: throw new Error('Unknown cmd '+cmd);
  }
  console.log(out);
  child.kill('SIGKILL'); process.exit(0);
})().catch(e=>{ console.error('ERR:', e.message, 'STDERR:', ebuf.slice(-500)); child.kill('SIGKILL'); process.exit(1); });
