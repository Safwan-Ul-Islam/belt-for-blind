// Wiring section: click any part, pin, wire or tag in the wiring picture to see what it connects to.
// The picture (docs/wiring-pictorial.svg) marks every part with data-part="..."; the ids are below.

const SIDES = {
  left: { name: 'Left', trig: 'D25', echo: 'D34', motor: 'D13' },
  center: { name: 'Center', trig: 'D26', echo: 'D35', motor: 'D33' },
  right: { name: 'Right', trig: 'D27', echo: 'D32', motor: 'D4' },
};
const each = make => Object.keys(SIDES).map(make);

const FIVE_VOLT = {
  title: '5V (ESP32 VIN)', kind: 'Power from USB, about 5V',
  rows: [['VIN', 'Left, Center and Right sensor VCC']],
  note: 'Only the ultrasonic sensors use 5V. Never connect the motors or the MPU6050 to it.',
  links: ['pin-VIN', 'net-5V', ...each(s => `sensor-${s}`)],
};
const THREE_VOLT = {
  title: '3V3 (ESP32 3V3)', kind: 'Power from the ESP32, 3.3V',
  rows: [['3V3', 'MPU6050 VCC'], ['3V3', 'Red wire of all 3 motors'], ['3V3', 'Stripe end of all 3 diodes']],
  note: 'Never let 3V3 touch GND, it cuts the power (short circuit).',
  links: ['pin-3V3', 'net-3V3', 'mpu', ...each(s => `motor-${s}`), ...each(s => `diode-${s}`)],
};
const GROUND = {
  title: 'GND (ground)', kind: 'Shared by every part',
  rows: [['Sensors', 'GND pin of all 3'], ['Dividers', 'Bottom leg of all 3 × 2kΩ'], ['MPU6050', 'GND'],
         ['MOSFETs', 'S (right leg) of all 3'], ['10kΩ', 'Bottom leg of all 3']],
  note: 'Every GND must be joined to the ESP32 GND, or the parts can\'t talk to each other.',
  links: ['pin-GND', 'net-GND', 'mpu', ...each(s => `sensor-${s}`), ...each(s => `r2k-${s}`),
          ...each(s => `mosfet-${s}`), ...each(s => `r10k-${s}`)],
};

const PARTS = {
  'pin-VIN': FIVE_VOLT, 'net-5V': FIVE_VOLT,
  'pin-3V3': THREE_VOLT, 'net-3V3': THREE_VOLT,
  'pin-GND': GROUND, 'net-GND': GROUND,
  esp32: {
    title: 'ESP32 DevKit', kind: 'The brain of the belt',
    rows: [['VIN · 3V3 · GND', 'Power'], ['D25 · D26 · D27', 'Sensor Trig'], ['D34 · D35 · D32', 'Sensor Echo'],
           ['D13 · D33 · D4', 'Motor MOSFETs'], ['D21 · D22', 'MPU6050 SDA · SCL']],
    note: 'Pin names are printed next to each pin on the board.',
    links: ['pin-VIN', 'pin-3V3', 'pin-GND', 'pin-D25', 'pin-D26', 'pin-D27', 'pin-D34', 'pin-D35', 'pin-D32',
            'pin-D13', 'pin-D33', 'pin-D4', 'pin-D21', 'pin-D22'],
  },
  mpu: {
    title: 'MPU6050 (GY-521)', kind: 'Tilt and motion sensor',
    rows: [['VCC', '3V3'], ['GND', 'GND'], ['SDA', 'ESP32 D21'], ['SCL', 'ESP32 D22'], ['XDA · XCL · AD0 · INT', 'Leave empty']],
    note: 'Fix it firmly: the belt uses its tilt to know when the wearer sits.',
    links: ['pin-3V3', 'pin-GND', 'pin-D21', 'pin-D22', 'net-3V3', 'net-GND'],
  },
  'pin-D21': { title: 'ESP32 pin D21', kind: 'I²C data', rows: [['D21', 'MPU6050 SDA']], links: ['mpu'] },
  'pin-D22': { title: 'ESP32 pin D22', kind: 'I²C clock', rows: [['D22', 'MPU6050 SCL']], links: ['mpu'] },
};

for (const [side, { name, trig, echo, motor }] of Object.entries(SIDES)) {
  Object.assign(PARTS, {
    [`sensor-${side}`]: {
      title: `${name} ultrasonic sensor`, kind: 'HC-SR04',
      rows: [['VCC', '5V (ESP32 VIN)'], ['GND', 'GND'], ['Trig', `ESP32 ${trig}`], ['Echo', `1kΩ → ESP32 ${echo}`]],
      note: 'Echo gives 5V, so the 1kΩ + 2kΩ pair lowers it to a safe 3.3V for the ESP32.',
      links: [`pin-${trig}`, `pin-${echo}`, `r1k-${side}`, `r2k-${side}`, 'net-5V'],
    },
    [`r1k-${side}`]: {
      title: `${name} 1kΩ resistor`, kind: 'Bands: brown · black · red · gold',
      rows: [['One leg', `${name} sensor Echo`], ['Other leg', `ESP32 ${echo} and the 2kΩ`]],
      note: 'Top half of the Echo voltage divider.',
      links: [`sensor-${side}`, `pin-${echo}`, `r2k-${side}`],
    },
    [`r2k-${side}`]: {
      title: `${name} 2kΩ resistor`, kind: 'Bands: red · black · red · gold',
      rows: [['One leg', `ESP32 ${echo} and the 1kΩ`], ['Other leg', 'GND']],
      note: 'Bottom half of the Echo voltage divider.',
      links: [`r1k-${side}`, `pin-${echo}`, 'net-GND'],
    },
    [`mosfet-${side}`]: {
      title: `${name} MOSFET (IRLZ44N)`, kind: 'Printed side facing you: legs G · D · S',
      rows: [['G · left leg', `ESP32 ${motor}, and the 10kΩ`], ['D · middle leg', 'Motor black wire, diode plain end'], ['S · right leg', 'GND']],
      note: `When ${motor} turns on, the MOSFET connects the motor to GND and it vibrates. No 220Ω needed.`,
      links: [`pin-${motor}`, `r10k-${side}`, `motor-${side}`, `diode-${side}`, 'net-GND'],
    },
    [`r10k-${side}`]: {
      title: `${name} 10kΩ resistor`, kind: 'Bands: brown · black · orange · gold',
      rows: [['One leg', 'MOSFET G (left leg)'], ['Other leg', 'GND']],
      note: 'Keeps the motor off while the ESP32 starts up.',
      links: [`mosfet-${side}`, `pin-${motor}`, 'net-GND'],
    },
    [`motor-${side}`]: {
      title: `${name} vibration motor`, kind: '3V coin motor',
      rows: [['Red wire', '3V3'], ['Black wire', 'MOSFET D (middle leg)']],
      note: `Vibrates when the ${name} sensor sees something too close. Never connect it to 5V.`,
      links: [`mosfet-${side}`, `diode-${side}`, 'net-3V3'],
    },
    [`diode-${side}`]: {
      title: `${name} diode (1N4007)`, kind: 'Black body with a silver stripe',
      rows: [['Stripe end', '3V3 (motor red)'], ['Plain end', 'MOSFET D (motor black)']],
      note: 'Sits across the motor to protect the MOSFET. If it is backwards, the motor won\'t run.',
      links: [`motor-${side}`, `mosfet-${side}`, 'net-3V3'],
    },
    [`pin-${trig}`]: {
      title: `ESP32 pin ${trig}`, kind: 'Sends the sound pulse',
      rows: [[trig, `${name} sensor Trig`]], links: [`sensor-${side}`],
    },
    [`pin-${echo}`]: {
      title: `ESP32 pin ${echo}`, kind: 'Hears the echo',
      rows: [[echo, `${name} sensor Echo, through the 1kΩ / 2kΩ divider`]],
      links: [`sensor-${side}`, `r1k-${side}`, `r2k-${side}`],
    },
    [`pin-${motor}`]: {
      title: `ESP32 pin ${motor}`, kind: `Switches the ${name.toLowerCase()} motor`,
      rows: [[motor, `${name} MOSFET G (left leg)`]],
      links: [`mosfet-${side}`, `r10k-${side}`, `motor-${side}`],
    },
  });
}

const diagram = document.querySelector('#wiring-diagram');
const info = document.querySelector('#wiring-info');
let svg;

function escape(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
}

function showIntro() {
  info.innerHTML = `
    <p class="eyebrow">CONNECTIONS</p>
    <h3>Click any part</h3>
    <p class="kind">A sensor, resistor, MOSFET, diode, motor, the MPU6050, an ESP32 pin, a wire or a
      5V / 3V3 / GND tag. Its connections appear here, and everything it connects to lights up.</p>`;
}

function select(id) {
  const part = PARTS[id];
  if (!svg || !part) return;
  const linked = new Set(part.links);
  svg.classList.add('choosing');
  for (const g of svg.querySelectorAll('[data-part]')) {
    g.classList.toggle('chosen', g.dataset.part === id);
    g.classList.toggle('linked', g.dataset.part !== id && linked.has(g.dataset.part));
  }
  const rows = part.rows.map(([a, b]) => `<tr><td>${escape(a)}</td><td>${escape(b)}</td></tr>`).join('');
  const chips = part.links.filter(l => PARTS[l] && PARTS[l] !== part && !l.startsWith('net-'))
    .map(l => `<button type="button" data-goto="${l}">${escape(PARTS[l].title)}</button>`).join('');
  info.innerHTML = `
    <p class="eyebrow">CONNECTIONS</p>
    <h3>${escape(part.title)}</h3>
    <p class="kind">${escape(part.kind)}</p>
    <table><tbody>${rows}</tbody></table>
    ${part.note ? `<p class="note">${escape(part.note)}</p>` : ''}
    ${chips ? `<p class="linked-title">Connected parts</p><div class="chips">${chips}</div>` : ''}
    <button type="button" class="clear" data-clear>Clear</button>`;
}

function clear() {
  if (!svg) return;
  svg.classList.remove('choosing');
  for (const g of svg.querySelectorAll('.chosen, .linked')) g.classList.remove('chosen', 'linked');
  showIntro();
}

info.addEventListener('click', event => {
  const target = event.target.closest('[data-goto], [data-clear]');
  if (!target) return;
  if (target.dataset.goto) select(target.dataset.goto); else clear();
});

async function load() {
  try {
    const response = await fetch('/wiring.svg');
    if (!response.ok) throw new Error(`status ${response.status}`);
    diagram.innerHTML = await response.text();
  } catch (error) {
    diagram.textContent = `The wiring picture could not load (${error.message}).`;
    return;
  }
  svg = diagram.querySelector('svg');
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  for (const g of svg.querySelectorAll('[data-part]')) {
    const part = PARTS[g.dataset.part];
    if (!part) continue;
    g.setAttribute('tabindex', '0');
    g.setAttribute('role', 'button');
    g.setAttribute('aria-label', part.title);
  }
  svg.addEventListener('click', event => {
    const g = event.target.closest('[data-part]');
    if (g) select(g.dataset.part); else clear();
  });
  svg.addEventListener('keydown', event => {
    const g = event.target.closest('[data-part]');
    if (g && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      select(g.dataset.part);
    }
  });
  showIntro();
  // A link like /3d#wiring/mosfet-left opens with that part selected
  const linked = decodeURIComponent(location.hash).match(/^#wiring\/(.+)$/);
  if (linked && PARTS[linked[1]]) select(linked[1]);
}

load();
