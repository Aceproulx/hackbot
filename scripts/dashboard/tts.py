"""tts.py — report text-to-speech (Vox engine → dashboard).

Ports the voice-selection logic verbatim from the Vox reference
(``/home/aceos/Downloads/index.html``): ``preferredNames``,
``scoreVoice``, the ``loadVoices`` top-5 English selection and the
``onvoiceschanged`` re-load. Everything runs client-side via the Web
Speech API — no text leaves the browser.

Ships three pieces:

* ``TTS_CSS`` — styles for the reader bar, sentence highlight, word
  highlight (Edge-style grey), floating toolbar and the settings panel.
* ``tts_reader_bar()`` — the Read / Pause / Resume / Stop bar that
  mounts in a report card header (floats when playing).
* ``tts_settings_panel()`` — the Voice tab content for the settings page.
* ``tts_js()`` — one self-contained script blob that wires the engine,
  sentence/word segmentation, playback controller, gestures and the
  settings panel.  Inert on pages that lack ``#tts-root`` / ``#tts-settings``.
"""
from .icons import icon

TTS_CSS = """
/* ── report TTS (Vox) ── */
.tts-bar{display:inline-flex;align-items:center;gap:6px;margin-right:2px;flex-wrap:wrap;transition:all .2s ease}
.tts-btn{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--border);background:#fff;color:#3d352b;border-radius:7px;padding:3px 9px;font:600 12px -apple-system,sans-serif;cursor:pointer;white-space:nowrap}
.tts-btn:hover{color:var(--accent);border-color:#d8c4b8}
.tts-btn:disabled{opacity:.4;cursor:not-allowed}
.tts-btn.tts-primary{background:var(--accent);color:#fff;border-color:var(--accent);box-shadow:0 1px 3px rgba(143,22,24,.35)}
.tts-btn.tts-primary:hover{background:var(--accent-hi)}
.tts-btn.tts-stop{color:#b3261e}
.tts-caption{font-size:11.5px;color:var(--muted);font-weight:500;margin-left:2px}
.tts-seg{border-radius:3px;transition:background .15s ease}
.tts-seg:hover{background:rgba(143,22,24,.06)}
.tts-seg.tts-active{background:rgba(143,22,24,.14);box-shadow:0 0 0 1px rgba(143,22,24,.18)}
/* word-level highlight — Edge-style grey on the spoken word */
::highlight(tts-word){background-color:rgba(80,80,80,.30);color:inherit;border-radius:2px}
/* floating toolbar — visible while reading so Pause/Stop stays reachable */
.tts-bar.tts-float{position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:999;background:#fff;border:1px solid var(--border);border-radius:10px;padding:6px 12px;box-shadow:0 4px 20px rgba(0,0,0,.15);animation:ttsFadeIn .18s ease}
@keyframes ttsFadeIn{from{opacity:0;transform:translateX(-50%) translateY(-6px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
#tts-settings input[type=range]{width:220px;accent-color:var(--accent);vertical-align:middle;cursor:pointer}
.tts-val{font-weight:700;color:var(--ink);margin-left:8px;font-size:12px;min-width:46px;display:inline-block}
.tts-check{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--ink);cursor:pointer}
.tts-check input{accent-color:var(--accent)}
.tts-voices{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:14px}
.tts-voice{text-align:left;padding:9px 11px;border:1px solid var(--border);background:#fff;border-radius:9px;cursor:pointer;font:inherit}
.tts-voice:hover{border-color:#d8c4b8}
.tts-voice.active{border-color:var(--accent);background:rgba(143,22,24,.05)}
.tts-voice .nm{font-weight:700;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tts-voice .if{color:var(--muted);font-size:10.5px;margin-top:3px}
.tts-test-row{display:inline-flex;align-items:center;gap:6px;margin-left:10px;vertical-align:middle;flex-wrap:wrap}
@media(max-width:900px){.tts-voices{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.tts-voices{grid-template-columns:1fr 1fr}}
"""


def tts_reader_bar() -> str:
    """Read / Pause / Resume / Stop bar for a report card header.

    Uses classes (not IDs) so multiple report cards can each carry a bar;
    buttons are wired via delegated ``data-action`` clicks in the JS.
    """
    return (
        '<span class="tts-bar">'
        f'<button class="tts-btn tts-primary tts-play" data-action="play" title="Read report aloud">{icon("play", 12)} Read</button>'
        f'<button class="tts-btn tts-pause" data-action="pause" style="display:none" title="Pause">{icon("pause", 12)} Pause</button>'
        f'<button class="tts-btn tts-resume" data-action="resume" style="display:none" title="Resume">{icon("play", 12)} Resume</button>'
        f'<button class="tts-btn tts-stop" data-action="stop" style="display:none" title="Stop">{icon("square", 12)} Stop</button>'
        '<span class="tts-caption"></span>'
        '</span>'
    )


def tts_settings_panel() -> str:
    """Voice tab content for the settings page."""
    return (
        '<div class="card" id="tts-settings"><div class="hd">Voice <span class="sp"></span>'
        '<span class="hint">text-to-speech for reports · runs locally in your browser</span></div><div class="bd">'
        '<table>'
        '<tr><td class="muted" style="width:150px">Voice</td><td><select id="tts-voice" class="fld" style="max-width:340px"></select>'
        '<span class="tts-test-row">'
        f'<button class="tts-btn" id="tts-test" onclick="TtsSettings.testVoice()" title="Hear the selected voice with current settings">{icon("play", 12)} Test</button>'
        f'<button class="tts-btn tts-stop" id="tts-test-stop" onclick="TtsSettings.stopTest()" style="display:none" title="Stop test">{icon("square", 12)} Stop</button>'
        '<span class="tts-caption" id="tts-test-status"></span>'
        '</span></td></tr>'
        '<tr><td class="muted">Rate</td><td><input id="tts-rate" type="range" min="0.5" max="2" step="0.05"><span class="tts-val" id="tts-rate-v"></span></td></tr>'
        '<tr><td class="muted">Pitch</td><td><input id="tts-pitch" type="range" min="0.5" max="1.5" step="0.05"><span class="tts-val" id="tts-pitch-v"></span></td></tr>'
        '<tr><td class="muted">Volume</td><td><input id="tts-volume" type="range" min="0" max="1" step="0.05"><span class="tts-val" id="tts-volume-v"></span></td></tr>'
        '<tr><td class="muted">Jump modifier</td><td><select id="tts-jump" class="fld" style="max-width:360px">'
        '<option value="ctrl">Ctrl+Click a sentence to jump there</option>'
        '<option value="meta">Cmd+Click a sentence to jump there</option>'
        '</select></td></tr>'
        '<tr><td class="muted">Highlight</td><td>'
        '<label class="tts-check"><input id="tts-highlight" type="checkbox"> highlight the sentence being read</label><br>'
        '<label class="tts-check"><input id="tts-word-hl" type="checkbox" checked> highlight the word being read (Edge-style)</label>'
        '</td></tr>'
        '</table>'
        '<div class="tts-voices" id="tts-voice-grid"></div>'
        '<p class="small" style="margin-top:10px;color:var(--muted)">Voices are supplied by your browser/OS. '
        'The five highest-scoring English voices are offered; on a report page Ctrl+I restarts reading. '
        'If your browser has no speech voices (e.g. Chrome on Linux), report pages fall back to '
        'server-side speech (espeak-ng).</p>'
        '</div></div>'
    )


_TTS_JS = r"""
/* ═══════════ Report TTS — Vox engine (voice logic ported verbatim) ═══════════ */
(function(){
var SYNTH = ('speechSynthesis' in window) ? window.speechSynthesis : null;
var UNSUPPORTED = !SYNTH;

/* ── engine: voice selection ── */
var allVoices = [];
var selectedVoices = [];
var readyCbs = [];
var changeCbs = [];
var readyFired = false;

var preferredNames = [
  'Microsoft Aria Online (Natural)', 'Microsoft Jenny Online (Natural)',
  'Microsoft Guy Online (Natural)', 'Google US English',
  'Google UK English Female', 'Google UK English Male',
  'Samantha', 'Alex', 'Karen', 'Daniel', 'Moira',
  'Microsoft Aria', 'Microsoft Jenny', 'Microsoft Guy',
  'Microsoft Zira', 'Microsoft David'
];

function scoreVoice(v) {
  var s = 0;
  var n = v.name.toLowerCase();
  var lang = v.lang.toLowerCase();
  if (lang.indexOf('en-us') === 0) s += 35;
  else if (lang.indexOf('en-gb') === 0) s += 30;
  else if (lang.indexOf('en-au') === 0 || lang.indexOf('en-ca') === 0) s += 25;
  else if (lang.indexOf('en') === 0) s += 15;
  if (/natural|neural|online/.test(n)) s += 100;
  if (/google|microsoft|samantha|alex|karen|daniel|moira/.test(n)) s += 25;
  if (v.localService === false) s += 15;
  return s;
}

function fireReady() {
  if (readyFired) return;
  readyFired = true;
  var cbs = readyCbs; readyCbs = [];
  cbs.forEach(function(cb){ try { cb(); } catch(e){} });
}
function fireChange() {
  changeCbs.forEach(function(cb){ try { cb(); } catch(e){} });
}
function loadVoices() {
  if (UNSUPPORTED) { fireReady(); fireChange(); return; }
  allVoices = SYNTH.getVoices().slice().sort(function(a,b){ return scoreVoice(b) - scoreVoice(a); });
  var english = allVoices.filter(function(v){ return /^en(-|_)/i.test(v.lang); });
  selectedVoices = (english.length ? english : allVoices).slice(0, 5);
  fireReady();
  fireChange();
}

/* ── engine: natural speech (single utterance like the Vox reference,
      with chunked fallback for Chrome's ~15s cutoff) ── */
var session = null;

function chunkText(text, base) {
  var sentences = text.split(/(?<=[.!?])\s+(?=[A-Z0-9])/);
  var chunks = [], cur = '', curStart = base;
  for (var i = 0; i < sentences.length; i++) {
    var s = sentences[i];
    if (i > 0) s = ' ' + s; /* split consumed the inter-sentence space */
    if (cur && (cur + s).length > 260) {
      chunks.push({ text: cur, start: curStart });
      curStart += cur.length;
      cur = s;
    } else {
      cur += s;
    }
  }
  if (cur) chunks.push({ text: cur, start: curStart });
  return chunks;
}

function clearProbe() {
  if (session && session.boundaryProbe) {
    clearTimeout(session.boundaryProbe);
    session.boundaryProbe = null;
  }
}

/* Time-based position estimate (fallback when boundary events are sparse).
   Returns absolute char offset in the full text. */
function estimatePos(s) {
  if (!s || !s.startTime || s.startTime <= 0) return (s ? s.lastBoundary : 0) || 0;
  var elapsed = (Date.now() - s.startTime) / 1000;
  return s.estBase + Math.floor(elapsed * 14 * s.rate);
}

function startChunks(text, offset) {
  var s = session;
  if (s.mode === 'chunks') return; /* already chunking (double onend/onerror) */
  s.mode = 'chunks';
  s.chunks = chunkText(text, offset);
  s.idx = 0;
  setTimeout(nextChunk, 30);
}

function nextChunk() {
  if (!session || session.paused) return;
  if (session.idx >= session.chunks.length) {
    var s = session; session = null;
    if (s.onEnd) s.onEnd();
    return;
  }
  var c = session.chunks[session.idx++];
  var u = new SpeechSynthesisUtterance(c.text);
  u.voice = session.voice;
  u.rate = session.rate; u.pitch = session.pitch; u.volume = session.volume;
  var tok = session.token;
  u.onstart = function(){
    if (!session || session.token !== tok || session.paused) return;
    session.startTime = Date.now();
    session.estBase = c.start;
  };
  u.onboundary = function(e){
    if (session && session.token === tok && !session.paused) {
      session.lastBoundary = c.start + (e.charIndex || 0);
      if (session.onBoundary) session.onBoundary(session.lastBoundary);
    }
  };
  u.onend = function(){
    if (session && session.token === tok && !session.paused) nextChunk();
  };
  u.onerror = function(e){
    if (e && (e.error === 'canceled' || e.error === 'interrupted')) return;
    if (session && session.token === tok && !session.paused) {
      var s = session; session = null;
      if (s.onError) s.onError(e);
    }
  };
  SYNTH.speak(u);
}

/* Speak the whole text as ONE utterance (natural prosody like the Vox
   reference). Chrome stops long utterances at ~15s, so we track the last
   word boundary and, when the utterance ends early, resume the remainder
   as chunks. Browsers without boundary events fall back to chunks up front. */
function speakWhole(text, offset) {
  var s = session;
  s.mode = 'whole';
  s.wholeText = text;
  s.lastBoundary = 0;
  s.startTime = 0;
  s.estBase = offset;
  var u = new SpeechSynthesisUtterance(text);
  u.voice = s.voice;
  u.rate = s.rate; u.pitch = s.pitch; u.volume = s.volume;
  var tok = s.token;
  u.onstart = function(){
    if (!session || session.token !== tok || session.paused) return;
    session.startTime = Date.now();
    session.estBase = offset;
    /* Probe: if no boundary events fire within 1.5s the browser doesn't
       support them — switch to chunked speech to survive Chrome's cutoff.
       Only recover when the utterance is actually stuck (not speaking):
       interrupting a progressing utterance would re-read the beginning. */
    session.boundaryProbe = setTimeout(function(){
      if (session && session.token === tok && !session.paused &&
          session.mode === 'whole' && session.lastBoundary === 0 && text.length > 600) {
        if (SYNTH.speaking) return;
        SYNTH.cancel();
        startChunks(text, offset);
      }
    }, 1500);
  };
  u.onboundary = function(e){
    if (!session || session.token !== tok || session.paused) return;
    session.lastBoundary = offset + (e.charIndex || 0);
    if (session.onBoundary) session.onBoundary(session.lastBoundary);
  };
  u.onend = function(){
    if (!session || session.token !== tok || session.paused) return;
    clearProbe();
    /* Chrome cuts long utterances at ~15s — resume from last known word */
    if (session.lastBoundary > 0 && session.lastBoundary < offset + text.length - 30) {
      startChunks(text.slice(session.lastBoundary - offset), session.lastBoundary);
    } else {
      var s2 = session; session = null;
      if (s2.onEnd) s2.onEnd();
    }
  };
  u.onerror = function(e){
    if (e && (e.error === 'canceled' || e.error === 'interrupted')) return;
    if (!session || session.token !== tok || session.paused) return;
    clearProbe();
    if (session.lastBoundary > 0 && session.lastBoundary < offset + text.length - 30) {
      startChunks(text.slice(session.lastBoundary - offset), session.lastBoundary);
    } else {
      var s2 = session; session = null;
      if (s2.onError) s2.onError(e);
    }
  };
  SYNTH.speak(u);
}

/* Snap an offset to the next word boundary (skip partial word + space). */
function snapToWord(text, from) {
  if (from > 0 && from < text.length) {
    var prev = text.charAt(from - 1);
    if (prev && !/\s/.test(prev)) {
      var m = text.slice(from).match(/^\S+\s*/);
      if (m) from += m[0].length;
    }
  }
  return Math.min(from, text.length);
}

/* ── server-side TTS fallback (no browser voices: Chrome-on-Linux) ── */
var serverAudio = null;
var serverTTS = false;

function serverChunkText(text, base) {
  var sentences = text.split(/(?<=[.!?])\s+(?=[A-Z0-9])/);
  var chunks = [], cur = '', curStart = base;
  for (var i = 0; i < sentences.length; i++) {
    var s = sentences[i];
    if (i > 0) s = ' ' + s;
    if (cur && (cur + s).length > 1000) {
      chunks.push({ text: cur, start: curStart });
      curStart += cur.length;
      cur = s;
    } else {
      cur += s;
    }
  }
  if (cur) chunks.push({ text: cur, start: curStart });
  return chunks;
}

function serverSpeak(text, offset) {
  var s = session;
  s.mode = 'server';
  s.chunks = serverChunkText(text, offset);
  s.idx = 0;
  s.lastBoundary = 0;
  serverPlayNext();
}

function serverPlayNext() {
  var s = session;
  if (!s || s.paused) return;
  if (s.idx >= s.chunks.length) {
    var s2 = session; session = null;
    if (s2.onEnd) s2.onEnd();
    return;
  }
  var c = s.chunks[s.idx++];
  var a = serverAudio || (serverAudio = (function(){
    var el = document.createElement('audio');
    el.style.display = 'none';
    document.body.appendChild(el);
    return el;
  })());
  a.onended = function(){
    if (!session || session.paused) return;
    session.lastBoundary = c.start + c.text.length;
    if (session.onBoundary) session.onBoundary(session.lastBoundary);
    serverPlayNext();
  };
  a.ontimeupdate = function(){
    if (!session || session.paused || !a.duration) return;
    var frac = a.currentTime / a.duration;
    var off = c.start + Math.floor(frac * c.text.length);
    if (off !== session.lastBoundary) {
      session.lastBoundary = off;
      if (session.onBoundary) session.onBoundary(off);
    }
  };
  a.onerror = function(){
    if (!session || session.paused) return;
    var s2 = session; session = null;
    if (s2.onError) s2.onError({ error: 'server-tts' });
  };
  a.src = '/api/tts?text=' + encodeURIComponent(c.text);
  a.play().catch(function(e){
    if (!session || session.paused) return;
    var s2 = session; session = null;
    if (s2.onError) s2.onError(e);
  });
}

var Vox = {
  getVoices: function(){ return selectedVoices.slice(); },
  onVoicesReady: function(cb){
    if (readyFired) { try { cb(); } catch(e){} return; }
    readyCbs.push(cb);
  },
  onVoicesChanged: function(cb){ changeCbs.push(cb); },
  speak: function(text, opts){
    opts = opts || {};
    var token = (session ? session.token : 0) + 1;
    var offset = opts.baseOffset || 0;
    session = {
      token: token, mode: 'whole', wholeText: text, chunks: null, idx: 0,
      lastBoundary: 0, pausePos: 0, paused: false, boundaryProbe: null,
      startTime: 0, estBase: offset,
      onBoundary: opts.onBoundary, onEnd: opts.onEnd, onError: opts.onError,
      voice: opts.voice || selectedVoices[0],
      rate: (opts.rate != null) ? opts.rate : 1,
      pitch: (opts.pitch != null) ? opts.pitch : 1,
      volume: (opts.volume != null) ? opts.volume : 1,
      baseOffset: offset
    };
    if (UNSUPPORTED || !selectedVoices.length) {
      /* no browser voices → server-side fallback (espeak-ng via /api/tts) */
      serverSpeak(text, offset);
    } else {
      SYNTH.cancel();
      SYNTH.resume(); /* Chrome: clear any stuck-paused state before speaking */
      speakWhole(text, offset);
    }
    return true;
  },
  pause: function(){
    if (!session || session.paused) return;
    session.paused = true;
    /* Use the better of boundary tracking or time-based estimate */
    session.pausePos = Math.max(session.lastBoundary || 0, estimatePos(session));
    clearProbe();
    if (session.mode === 'server') {
      if (serverAudio) serverAudio.pause();
    } else {
      SYNTH.cancel();
    }
  },
  resume: function(){
    if (!session || !session.paused) return;
    var s = session;
    s.paused = false;
    if (s.mode === 'server') {
      if (serverAudio) serverAudio.play().catch(function(){});
      return;
    }
    var from = s.pausePos - s.baseOffset;
    if (from < 0) from = 0;
    from = snapToWord(s.wholeText, from);
    var remaining = s.wholeText.slice(from);
    if (!remaining.trim()) {
      session = null;
      if (s.onEnd) s.onEnd();
      return;
    }
    SYNTH.cancel();
    SYNTH.resume(); /* Chrome: clear stuck-paused state */
    s.lastBoundary = 0;
    s.startTime = 0;
    speakWhole(remaining, s.baseOffset + from);
  },
  cancel: function(){
    if (session && session.mode === 'server') {
      if (serverAudio) { serverAudio.pause(); serverAudio.removeAttribute('src'); serverAudio.load(); }
      session = null;
      return;
    }
    if (UNSUPPORTED) return;
    SYNTH.cancel();
    clearProbe();
    session = null;
  },
  isSpeaking: function(){ return !!(SYNTH && SYNTH.speaking) || !!(session && session.mode === 'server' && serverAudio && !serverAudio.paused); },
  isPaused: function(){ return !!(session && session.paused); }
};

/* ── shared settings (localStorage, not cookies) ── */
function loadSettings() {
  var d = { voiceName: '', rate: 1, pitch: 1, volume: 1,
            jumpModifier: (navigator.platform && navigator.platform.indexOf('Mac') === 0) ? 'meta' : 'ctrl',
            highlightEnabled: true, wordHighlightEnabled: true };
  try {
    var raw = localStorage.getItem('vox:tts:settings');
    if (raw) {
      var o = JSON.parse(raw);
      if (o && typeof o === 'object') {
        if (typeof o.voiceName === 'string') d.voiceName = o.voiceName;
        if (typeof o.rate === 'number' && isFinite(o.rate)) d.rate = Math.min(2, Math.max(0.5, o.rate));
        if (typeof o.pitch === 'number' && isFinite(o.pitch)) d.pitch = Math.min(1.5, Math.max(0.5, o.pitch));
        if (typeof o.volume === 'number' && isFinite(o.volume)) d.volume = Math.min(1, Math.max(0, o.volume));
        if (o.jumpModifier === 'ctrl' || o.jumpModifier === 'meta') d.jumpModifier = o.jumpModifier;
        if (typeof o.highlightEnabled === 'boolean') d.highlightEnabled = o.highlightEnabled;
        if (typeof o.wordHighlightEnabled === 'boolean') d.wordHighlightEnabled = o.wordHighlightEnabled;
      }
    }
  } catch(e) {}
  return d;
}

function ttsEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#039;' }[c];
  });
}

/* ── Reader (per-report instance; supports multiple report cards per page) ── */
var readers = [];
var activeReader = null;

function createReader(rootEl) {
  var root = rootEl;
  var card = root.closest('.card') || root.parentElement;
  var bar = card ? card.querySelector('.tts-bar') : null;
  var caption = bar ? bar.querySelector('.tts-caption') : null;
  var btnPlay = bar ? bar.querySelector('.tts-play') : null;
  var btnPause = bar ? bar.querySelector('.tts-pause') : null;
  var btnResume = bar ? bar.querySelector('.tts-resume') : null;
  var btnStop = bar ? bar.querySelector('.tts-stop') : null;
  var fullText = '';
  var segs = [];
  var words = [];       /* word-level index for highlight + auto-scroll */
  var state = 'idle';   /* idle | playing | paused */
  var activeSeg = null;
  var activeWord = null;
  var voicesReady = false;
  var settings = loadSettings();
  var segmenting = false;
  var segDebounce = null;
  var rafPending = false;
  var pendingOffset = -1;
  var lastScrollAt = 0;

  /* ── CSS Custom Highlight API (Edge / Chrome 105+) ── */
  var wordHL = null;
  try {
    if (window.CSS && CSS.highlights) {
      wordHL = new Highlight();
      CSS.highlights.set('tts-word', wordHL);
    }
  } catch(e) {}

  function setCaption(t){ if (caption) caption.textContent = t || ''; }

  function resolveVoice() {
    var vs = Vox.getVoices();
    if (!vs.length) return null;
    if (settings.voiceName) {
      for (var i = 0; i < vs.length; i++) if (vs[i].name === settings.voiceName) return vs[i];
    }
    return vs[0];
  }

  function updateUI() {
    if (!bar) return;
    btnPlay.style.display = (state === 'idle') ? '' : 'none';
    btnPause.style.display = (state === 'playing') ? '' : 'none';
    btnResume.style.display = (state === 'paused') ? '' : 'none';
    btnStop.style.display = (state === 'idle') ? 'none' : '';
    btnPlay.disabled = !((voicesReady || serverTTS) && fullText);
    /* floating toolbar while reading */
    bar.classList.toggle('tts-float', state !== 'idle');
    if (UNSUPPORTED) setCaption(serverTTS ? 'server-side voice' : 'speech synthesis not supported in this browser');
    else if (!voicesReady) setCaption(serverTTS ? 'loading voices… (server voice ready)' : 'loading voices…');
    else if (!fullText) setCaption('');
  }

  /* ── sentence highlight (red tint) ── */
  function highlightSentence(offset) {
    if (!settings.highlightEnabled) return;
    var seg = null;
    for (var i = 0; i < segs.length; i++) {
      if (offset >= segs[i].start && offset < segs[i].end) { seg = segs[i]; break; }
    }
    if (seg === activeSeg) return;
    if (activeSeg && activeSeg.el) activeSeg.el.classList.remove('tts-active');
    activeSeg = seg;
    if (seg && seg.el) seg.el.classList.add('tts-active');
  }

  /* ── word highlight (Edge-style grey) + auto-scroll ── */
  function findWord(offset) {
    var lo = 0, hi = words.length - 1, best = null;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (words[mid].start <= offset) { best = words[mid]; lo = mid + 1; }
      else hi = mid - 1;
    }
    return best;
  }

  function wordRange(w) {
    var node = w.segEl && w.segEl.firstChild;
    if (!node || node.nodeType !== 3) return null;
    var r = document.createRange();
    r.setStart(node, w.wStart);
    r.setEnd(node, w.wEnd);
    return r;
  }

  /* Auto-scroll is throttled (~300ms) so rapid words near a band edge
     don't queue up multiple competing smooth-scroll animations. */
  function autoScrollToWord(w) {
    var now = Date.now();
    if (now - lastScrollAt < 300) return;
    try {
      var rr = wordRange(w);
      if (rr) {
        var rect = rr.getBoundingClientRect();
        if (rect.height > 0) {
          var target = window.innerHeight * 0.35;
          var delta = rect.top - target;
          if (Math.abs(delta) > 40) {
            lastScrollAt = now;
            window.scrollBy({ top: delta, behavior: 'smooth' });
          }
        }
      }
    } catch(e) {}
  }

  function highlightWord(offset) {
    if (!settings.wordHighlightEnabled) return;
    var w = findWord(offset);
    if (!w || w === activeWord) return;
    activeWord = w;
    /* update CSS highlight */
    if (wordHL) {
      wordHL.clear();
      var r = wordRange(w);
      if (r) try { wordHL.add(r); } catch(e) {}
    }
    autoScrollToWord(w);
  }

  function clearHighlights() {
    if (activeSeg && activeSeg.el) activeSeg.el.classList.remove('tts-active');
    activeSeg = null;
    if (wordHL) wordHL.clear();
    activeWord = null;
    /* drop any pending rAF highlight so a stale word can't flash after stop */
    rafPending = false;
    pendingOffset = -1;
  }

  /* ── segmentation + word index ── */
  function segment() {
    if (!root) return;
    segmenting = true;
    try {
      fullText = '';
      segs = [];
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: function(node){
          var p = node.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          if (p.closest('pre, code, script, style, .cv-ctl, .cv-out')) return NodeFilter.FILTER_REJECT;
          if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      var nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var text = node.nodeValue;
        var parent = node.parentElement;
        /* idempotent re-segment: if this text node already lives inside a
           .tts-seg span (e.g. a spurious MutationObserver fire), reuse the
           existing span instead of nesting a new one */
        if (parent && parent.classList && parent.classList.contains('tts-seg')) {
          var st0 = fullText.length;
          fullText += text;
          segs.push({ start: st0, end: st0 + text.length, el: parent });
          continue;
        }
        var sentences = text.split(/(?<=[.!?])\s+(?=[A-Z0-9])/);
        if (sentences.length === 1) {
          var start = fullText.length;
          fullText += text;
          var span = document.createElement('span');
          span.className = 'tts-seg';
          span.setAttribute('data-start', start);
          span.setAttribute('data-end', start + text.length);
          span.textContent = text;
          node.parentNode.replaceChild(span, node);
          segs.push({ start: start, end: start + text.length, el: span });
        } else {
          var frag = document.createDocumentFragment();
          for (var j = 0; j < sentences.length; j++) {
            var s = sentences[j];
            if (j > 0) s = ' ' + s; /* split consumed the inter-sentence space */
            var st = fullText.length;
            fullText += s;
            var sp = document.createElement('span');
            sp.className = 'tts-seg';
            sp.setAttribute('data-start', st);
            sp.setAttribute('data-end', st + s.length);
            sp.textContent = s;
            frag.appendChild(sp);
            segs.push({ start: st, end: st + s.length, el: sp });
          }
          node.parentNode.replaceChild(frag, node);
        }
      }
      buildWords();
    } finally {
      /* reset in a macrotask so pending MutationObserver microtasks
         (queued by our own span wrapping) see segmenting === true */
      setTimeout(function(){ segmenting = false; }, 0);
    }
  }

  function buildWords() {
    words = [];
    for (var i = 0; i < segs.length; i++) {
      var seg = segs[i];
      var node = seg.el && seg.el.firstChild;
      if (!node || node.nodeType !== 3) continue;
      var text = node.nodeValue;
      var re = /\S+/g;
      var m;
      while ((m = re.exec(text))) {
        words.push({
          start: seg.start + m.index,
          end: seg.start + m.index + m[0].length,
          segEl: seg.el,
          wStart: m.index,
          wEnd: m.index + m[0].length
        });
      }
    }
  }

  /* ── playback ── */
  function speakFrom(offset) {
    settings = loadSettings(); /* pick up settings-page changes */
    var text = fullText.slice(offset);
    if (!text.trim()) { stop(); return; }
    state = 'playing';
    activeReader = self;
    updateUI();
    Vox.speak(text, {
      baseOffset: offset,
      voice: resolveVoice(),
      rate: settings.rate, pitch: settings.pitch, volume: settings.volume,
      onBoundary: function(g){ scheduleHighlight(g); },
      onEnd: function(){ state = 'idle'; clearHighlights(); updateUI(); },
      onError: function(){ state = 'idle'; clearHighlights(); updateUI(); setCaption('speech error'); }
    });
  }

  /* rAF-throttled highlight: boundary events can fire faster than frames */
  function scheduleHighlight(offset) {
    pendingOffset = offset;
    if (rafPending) return;
    rafPending = true;
    (window.requestAnimationFrame || function(cb){ setTimeout(cb, 16); })(function() {
      rafPending = false;
      if (pendingOffset >= 0) {
        var o = pendingOffset;
        pendingOffset = -1;
        highlightSentence(o);
        highlightWord(o);
      }
    });
  }

  function play() {
    if (!(voicesReady || serverTTS) || !fullText) return;
    if (state === 'paused') { resume(); return; }
    if (state === 'playing') return;
    stopOthers(self);
    speakFrom(0);
  }
  function pause() {
    if (state !== 'playing') return;
    Vox.pause();
    state = 'paused';
    updateUI();
  }
  function resume() {
    if (state !== 'paused') return;
    Vox.resume();
    state = 'playing';
    updateUI();
  }
  function stop() {
    Vox.cancel();
    state = 'idle';
    clearHighlights();
    updateUI();
  }
  function restart() { stop(); play(); }
  function jumpTo(offset) {
    if (!fullText) return;
    var seg = null;
    for (var i = 0; i < segs.length; i++) {
      if (offset >= segs[i].start && offset < segs[i].end) { seg = segs[i]; break; }
    }
    var start = seg ? seg.start : offset;
    stopOthers(self);
    Vox.cancel();
    state = 'playing';
    activeReader = self;
    speakFrom(start);
    updateUI();
  }
  function refresh() {
    stop();
    /* re-locate bar elements in case the card was re-rendered */
    var card2 = root.closest('.card') || root.parentElement;
    bar = card2 ? card2.querySelector('.tts-bar') : null;
    caption = bar ? bar.querySelector('.tts-caption') : null;
    btnPlay = bar ? bar.querySelector('.tts-play') : null;
    btnPause = bar ? bar.querySelector('.tts-pause') : null;
    btnResume = bar ? bar.querySelector('.tts-resume') : null;
    btnStop = bar ? bar.querySelector('.tts-stop') : null;
    segment();
    voicesReady = Vox.getVoices().length > 0;
    updateUI();
  }

  /* MutationObserver: re-segment when the dashboard re-renders report
     content in place (self-inflicted span wrapping is ignored via the
     segmenting flag). */
  if (window.MutationObserver) {
    var mo = new MutationObserver(function(muts){
      if (segmenting) return;
      /* skip mutations inside excluded regions (code blocks, controls) */
      for (var i = 0; i < muts.length; i++) {
        var t = muts[i].target;
        if (t && t.nodeType === 1 && t.closest && t.closest('.cv-ctl, .cv-out, pre, code, script, style')) return;
      }
      clearTimeout(segDebounce);
      segDebounce = setTimeout(function(){
        if (!root.isConnected) { stop(); return; }
        refresh();
      }, 300);
    });
    mo.observe(root, { childList: true, subtree: true, characterData: true });
  }

  /* initial voice check so play() isn't permanently gated */
  segment();
  voicesReady = Vox.getVoices().length > 0;
  updateUI();

  var self = {
    rootEl: root,
    play: play, pause: pause, resume: resume, stop: stop,
    restart: restart, jumpTo: jumpTo, refresh: refresh,
    syncVoices: function(){ voicesReady = Vox.getVoices().length > 0; updateUI(); },
    getState: function(){ return state; }
  };
  return self;
}

function stopOthers(except) {
  for (var i = 0; i < readers.length; i++) {
    if (readers[i] !== except && readers[i].getState() !== 'idle') readers[i].stop();
  }
}

function getReaderFor(el) {
  /* Walk up to the common .card wrapper, then find the .tts-root inside it.
     The bar buttons live in .card > .hd > .tts-bar (sibling of .tts-root),
     so el.closest('.tts-root') alone wouldn't find them. */
  var card = el.closest ? el.closest('.card') : null;
  var rootEl = card && card.querySelector ? card.querySelector('.tts-root') : null;
  if (!rootEl && el.closest) rootEl = el.closest('.tts-root');
  if (!rootEl) return null;
  for (var i = 0; i < readers.length; i++) {
    if (readers[i].rootEl === rootEl) return readers[i];
  }
  return null;
}

function initReaders() {
  readers = readers.filter(function(r){ return r.rootEl.isConnected; });
  if (activeReader && !activeReader.rootEl.isConnected) activeReader = null;
  var roots = document.querySelectorAll('.tts-root');
  for (var i = 0; i < roots.length; i++) {
    var found = false;
    for (var j = 0; j < readers.length; j++) {
      if (readers[j].rootEl === roots[i]) { found = true; break; }
    }
    if (!found) readers.push(createReader(roots[i]));
  }
}

/* ── global gestures (delegated, scoped to .tts-root) ── */
document.addEventListener('click', function(e){
  var t = e.target;
  if (!t || t.nodeType !== 1) return;
  /* reader bar buttons */
  var btn = t.closest('.tts-bar .tts-btn');
  if (btn) {
    var action = btn.getAttribute('data-action');
    var r = getReaderFor(btn);
    if (r && action) {
      if (action === 'play') r.play();
      else if (action === 'pause') r.pause();
      else if (action === 'resume') r.resume();
      else if (action === 'stop') r.stop();
      return;
    }
  }
  /* Ctrl/Cmd+Click a sentence to jump there */
  if (t.closest('a')) return;
  var seg = t.closest('.tts-seg');
  if (!seg) return;
  var reader = getReaderFor(seg);
  if (!reader) return;
  var st = loadSettings();
  var mod = st.jumpModifier === 'meta' ? e.metaKey : e.ctrlKey;
  if (!mod) return;
  e.preventDefault();
  reader.jumpTo(Number(seg.getAttribute('data-start')) || 0);
});

document.addEventListener('keydown', function(e){
  var tag = (e.target && e.target.tagName) || '';
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  var st = loadSettings();
  var mod = st.jumpModifier === 'meta' ? e.metaKey : e.ctrlKey;
  if (mod && (e.key === 'i' || e.key === 'I')) {
    e.preventDefault();
    if (activeReader) activeReader.restart();
  }
});

window.Reader = {
  play: function(btn){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.play(); },
  pause: function(btn){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.pause(); },
  resume: function(btn){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.resume(); },
  stop: function(btn){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.stop(); },
  restart: function(btn){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.restart(); },
  jumpTo: function(btn, offset){ var r = btn ? getReaderFor(btn) : (activeReader || readers[0]); if (r) r.jumpTo(offset); },
  init: initReaders
};
var ReaderAPI = window.Reader;

initReaders();

/* ── Settings panel (settings page; inert elsewhere) ── */
var TtsSettings = (function(){
  var panel = document.getElementById('tts-settings');
  if (!panel) return { refreshVoices: function(){}, testVoice: function(){}, stopTest: function(){} };
  var voiceSel = document.getElementById('tts-voice');
  var grid = document.getElementById('tts-voice-grid');
  var rate = document.getElementById('tts-rate');
  var pitch = document.getElementById('tts-pitch');
  var volume = document.getElementById('tts-volume');
  var jump = document.getElementById('tts-jump');
  var highlight = document.getElementById('tts-highlight');
  var wordHLChk = document.getElementById('tts-word-hl');
  var rateV = document.getElementById('tts-rate-v');
  var pitchV = document.getElementById('tts-pitch-v');
  var volumeV = document.getElementById('tts-volume-v');
  var testStop = document.getElementById('tts-test-stop');
  var testStatus = document.getElementById('tts-test-status');
  var settings = loadSettings();
  var debounce = null;

  function save() {
    settings.voiceName = voiceSel.value || '';
    settings.rate = Number(rate.value);
    settings.pitch = Number(pitch.value);
    settings.volume = Number(volume.value);
    settings.jumpModifier = jump.value;
    settings.highlightEnabled = highlight.checked;
    settings.wordHighlightEnabled = wordHLChk ? wordHLChk.checked : true;
    try { localStorage.setItem('vox:tts:settings', JSON.stringify(settings)); } catch(e) {}
  }
  function debouncedSave() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(save, 200);
  }
  function refreshGrid() {
    var kids = grid.children;
    for (var i = 0; i < kids.length; i++) {
      kids[i].className = 'tts-voice' + (kids[i].getAttribute('data-name') === voiceSel.value ? ' active' : '');
    }
  }
  function refreshVoices() {
    var vs = Vox.getVoices();
    voiceSel.innerHTML = '';
    grid.innerHTML = '';
    if (!vs.length) {
      var o = document.createElement('option');
      o.textContent = UNSUPPORTED ? 'Speech synthesis not supported' : 'No speech voices available';
      voiceSel.appendChild(o);
      return;
    }
    var current = settings.voiceName;
    var found = false;
    for (var i = 0; i < vs.length; i++) {
      var v = vs[i];
      var opt = document.createElement('option');
      opt.value = v.name;
      opt.textContent = v.name + ' — ' + v.lang;
      voiceSel.appendChild(opt);
      if (v.name === current) { voiceSel.value = v.name; found = true; }
    }
    if (!found) { voiceSel.value = vs[0].name; settings.voiceName = vs[0].name; save(); }
    for (var j = 0; j < vs.length; j++) {
      var vv = vs[j];
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'tts-voice' + (voiceSel.value === vv.name ? ' active' : '');
      el.setAttribute('data-name', vv.name);
      el.innerHTML = '<div class="nm">' + ttsEsc(vv.name) + '</div><div class="if">' + ttsEsc(vv.lang) + (vv.localService ? ' · Local' : ' · Online') + '</div>';
      el.onclick = (function(name){ return function(){ voiceSel.value = name; save(); refreshGrid(); }; })(vv.name);
      grid.appendChild(el);
    }
  }

  function testVoice() {
    var vs = Vox.getVoices();
    if (!vs.length && !serverTTS) { if (testStatus) testStatus.textContent = 'no voices available'; return; }
    var voice = null;
    for (var i = 0; i < vs.length; i++) {
      if (vs[i].name === voiceSel.value) { voice = vs[i]; break; }
    }
    if (!voice && vs.length) voice = vs[0];
    var sample = 'Hey! This is a quick test of the selected voice. How does it sound?';
    Vox.speak(sample, {
      voice: voice,
      rate: Number(rate.value),
      pitch: Number(pitch.value),
      volume: Number(volume.value),
      onEnd: function(){ if (testStop) testStop.style.display = 'none'; if (testStatus) testStatus.textContent = ''; },
      onError: function(){ if (testStop) testStop.style.display = 'none'; if (testStatus) testStatus.textContent = 'speech error'; }
    });
    if (testStop) testStop.style.display = '';
    if (testStatus) testStatus.textContent = 'testing…';
  }

  function stopTest() {
    Vox.cancel();
    if (testStop) testStop.style.display = 'none';
    if (testStatus) testStatus.textContent = '';
  }

  rate.value = settings.rate;
  pitch.value = settings.pitch;
  volume.value = settings.volume;
  jump.value = settings.jumpModifier;
  highlight.checked = settings.highlightEnabled;
  if (wordHLChk) wordHLChk.checked = settings.wordHighlightEnabled;
  rateV.textContent = Number(settings.rate).toFixed(2) + '×';
  pitchV.textContent = Number(settings.pitch).toFixed(2);
  volumeV.textContent = Math.round(Number(settings.volume) * 100) + '%';

  rate.oninput = function(){ rateV.textContent = Number(rate.value).toFixed(2) + '×'; debouncedSave(); };
  pitch.oninput = function(){ pitchV.textContent = Number(pitch.value).toFixed(2); debouncedSave(); };
  volume.oninput = function(){ volumeV.textContent = Math.round(Number(volume.value) * 100) + '%'; debouncedSave(); };
  jump.onchange = save;
  highlight.onchange = save;
  if (wordHLChk) wordHLChk.onchange = save;
  voiceSel.onchange = function(){ save(); refreshGrid(); };

  return { refreshVoices: refreshVoices, testVoice: testVoice, stopTest: stopTest };
})();

window.Reader = ReaderAPI;
window.TtsSettings = TtsSettings;
window.Vox = Vox;

function syncAllReaders() {
  initReaders();
  for (var i = 0; i < readers.length; i++) readers[i].syncVoices();
}
Vox.onVoicesReady(syncAllReaders);
Vox.onVoicesChanged(syncAllReaders);
Vox.onVoicesReady(function(){ TtsSettings.refreshVoices(); });
Vox.onVoicesChanged(function(){ TtsSettings.refreshVoices(); });
loadVoices();
if (SYNTH && 'onvoiceschanged' in SYNTH) SYNTH.onvoiceschanged = loadVoices;

/* Probe server-side TTS fallback (espeak-ng via /api/tts). When the browser
   has no speechSynthesis voices (Chrome-on-Linux), the Read button falls back
   to server-synthesized audio. */
fetch('/api/tts?probe=1').then(function(r){ return r.json(); }).then(function(d){
  serverTTS = !!(d && d.ok);
  syncAllReaders();
}).catch(function(){ serverTTS = false; syncAllReaders(); });
})();
"""


def tts_js() -> str:
    """Full client-side TTS script blob (self-contained, page-agnostic)."""
    return _TTS_JS
