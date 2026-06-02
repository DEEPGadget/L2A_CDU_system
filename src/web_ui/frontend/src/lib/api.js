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
  getState()                    { return request('/api/state'); },
  // Prometheus range query proxy → { resultType:'matrix', result:[{metric,values}] }
  getHistory(query, minutes, step) {
    const qs = new URLSearchParams({ query, minutes, step }).toString();
    return request(`/api/history?${qs}`);
  }
};
