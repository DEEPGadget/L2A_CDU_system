// Shared live Redis state, hydrated via GET /api/state then kept current over
// the /ws WebSocket. Singleton: safe to call startLive() from multiple pages.
import { api } from './api.js';

export const live = $state({ data: {}, connected: false });

let ws = null;
let started = false;

export function startLive() {
  if (started) return;
  started = true;
  hydrate();
  connect();
}

async function hydrate() {
  try {
    const snap = await api.getState();
    live.data = { ...snap };
  } catch {
    // ignore — the WebSocket will fill values in as they update
  }
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { live.connected = true; };
  ws.onclose = () => { live.connected = false; setTimeout(connect, 2000); };
  ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    const { key, value } = msg;
    if (value === null) {
      const next = { ...live.data };
      delete next[key];
      live.data = next;
    } else {
      live.data = { ...live.data, [key]: value };
    }
  };
}
