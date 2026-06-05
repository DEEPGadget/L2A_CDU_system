// Thin fetch wrapper. Throws on non-2xx so callers can `try/catch` without
// remembering to check response.ok.
async function request(path, init) {
  const res = await fetch(path, {
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    ...init
  });
  if (!res.ok) {
    let detail = '';
    try { detail = await res.text(); } catch { /* ignore */ }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  getControl()                  { return request('/api/control'); },
  putMode(mode)                 { return request('/api/control/mode',      { method: 'PUT', body: JSON.stringify({ mode }) }); },
  putFanCurve(fanCurve)         { return request('/api/control/fan_curve', { method: 'PUT', body: JSON.stringify(fanCurve) }); },
  putPumpDuty(duty)             { return request('/api/control/pump_duty', { method: 'PUT', body: JSON.stringify({ duty }) }); },
  // Manual per-actuator PWM duty (UI %). Pass any subset: {pump_1,pump_2,fan_1,fan_2}
  putDuty(duty)                 { return request('/api/control/duty',      { method: 'PUT', body: JSON.stringify(duty) }); },
  getState()                    { return request('/api/state'); },
  // Raw cooling diagram SVG (with {TOKEN} placeholders) — single source w/ Local UI
  getDiagram()                  { return fetch('/api/diagram').then((r) => r.text()); },
  // Prometheus range query proxy → { resultType:'matrix', result:[{metric,values}] }
  // opts: { minutes, step } OR { start, end, step } (unix seconds for custom range)
  getHistory(query, opts = {}) {
    const p = { query, step: opts.step ?? 30 };
    if (opts.start != null && opts.end != null) { p.start = opts.start; p.end = opts.end; }
    else { p.minutes = opts.minutes ?? 60; }
    return request(`/api/history?${new URLSearchParams(p).toString()}`);
  }
};
