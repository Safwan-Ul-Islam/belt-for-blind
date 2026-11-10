export const SENSOR_NAMES = ['Left', 'Center', 'Right'];
export const STALE_SECONDS = 3;
export const ALERT_CM = { Left: 15, Center: 30, Right: 15 };
export const COLORS = {
  'too-close': '#e5484d', 'very-close': '#ea6a12', close: '#facc15',
  far: '#34c26f', clear: '#5aa9ff', nosignal: '#8b95a3',
};

export function zoneOf(cm) {
  return cm < 15 ? 'too-close' : cm < 50 ? 'very-close' : cm < 150 ? 'close' : 'far';
}

export function isLive(snapshot, receivedAt, now) {
  return Boolean(snapshot?.connected && Number.isFinite(snapshot.age) && snapshot.age >= 0 &&
    snapshot.age + Math.max(0, now - receivedAt) < STALE_SECONDS);
}

export function sensorState(snapshot, name, live) {
  const reading = !live ? null : snapshot.sitting ? { status: 'paused' } : snapshot.sensors?.[name];
  const status = reading?.status || 'waiting';
  const ok = status === 'ok' && Number.isFinite(reading.cm);
  return {
    status, cm: ok ? reading.cm : null,
    zone: ok ? zoneOf(reading.cm) : status === 'clear' ? 'clear' : 'nosignal',
    // Blender's beams use mm under a root scaled to metres, capped at 2 m.
    length: ok ? Math.min(reading.cm, 200) * 10 : status === 'clear' ? 300 : null,
    alert: ok && reading.cm < ALERT_CM[name],
    motor: Boolean(live && !snapshot.sitting && snapshot.motors?.[name]),
    label: ok ? `${reading.cm} cm` : ({ clear: 'Clear', paused: 'Paused', nosignal: 'No signal' }[status] || 'Waiting'),
  };
}
