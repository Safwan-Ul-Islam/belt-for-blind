import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { BeltOrientation } from './orientation.js';
import { ALERT_CM, COLORS, SENSOR_NAMES, isLive, sensorState } from './live-state.js';

const $ = selector => document.querySelector(selector);
const viewport = $('#viewport');
const scene = new THREE.Scene();
const studioColor = new THREE.Color('#b6c1b7');
scene.background = studioColor;
const camera = new THREE.PerspectiveCamera(45, 1, 0.001, 100);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1;
renderer.outputColorSpace = THREE.SRGBColorSpace;
viewport.append(renderer.domElement);
renderer.domElement.setAttribute('aria-hidden', 'true');
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.07;
controls.maxDistance = 5;
controls.screenSpacePanning = true;

// Blender's soft key and sun, plus fallback illumination if the optional HDRI
// hasn't been downloaded. The fallback is removed once the workshop is ready.
const fallback = new THREE.HemisphereLight(0xf8fcff, 0x5e6854, 2.5);
fallback.up.set(0, 0, 1);
fallback.position.set(0, 0, 1);
scene.add(fallback);
const sun = new THREE.DirectionalLight(0xfff8ef, 1.2);
sun.position.set(-0.25, -0.35, 0.8);
scene.add(sun);
const key = new THREE.DirectionalLight(0xffffff, 1.3);
key.position.set(0.1, -0.15, 0.5);
scene.add(key);

let root, environment, config, orientation;
let snapshot = null, receivedAt = 0, transportDown = false;
let showBeams = true, showWorkshop = true;
const objects = new Map();
const sensors = new Map();
const motors = new Map();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const connection = $('#connection');
const liveDetail = $('#live-detail');

function resetView() {
  camera.position.fromArray(config.camera);
  controls.target.fromArray(config.target);
  controls.update();
}

function resize() {
  const { width, height } = viewport.getBoundingClientRect();
  camera.aspect = width / height;
  // Preserve Blender's horizontal field of view on wide screens. On phones,
  // leave room above the controls and below the title for the whole prototype.
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(config?.fov || 48) / 2) / camera.aspect));
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}
new ResizeObserver(resize).observe(viewport);

function makeLabel(name, position) {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 160;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.position.set(...position);
  sprite.scale.set(60, 18.75, 1);
  sprite.renderOrder = 5;
  root.add(sprite);
  let previous;
  return { sprite, update(text, color) {
    const value = `${text}|${color}`;
    if (value === previous) return;
    previous = value;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, 512, 160);
    ctx.fillStyle = '#f9faf4ed';
    ctx.beginPath(); ctx.roundRect(4, 4, 504, 152, 28); ctx.fill();
    ctx.textAlign = 'center'; ctx.fillStyle = '#52604f';
    ctx.font = '500 30px system-ui'; ctx.fillText(name.toUpperCase(), 256, 50);
    ctx.fillStyle = color; ctx.font = '600 55px system-ui'; ctx.fillText(text, 256, 116);
    texture.needsUpdate = true;
  } };
}

function eachMaterial(object, callback) {
  object.traverse(child => {
    if (child.isMesh) for (const material of Array.isArray(child.material) ? child.material : [child.material]) callback(material);
  });
}

function setupModel(gltf) {
  gltf.scene.traverse(object => {
    if (object.userData.belt_name) objects.set(object.userData.belt_name, object);
  });
  root = objects.get('Belt for Blind (mm)');
  if (!root) throw new Error('The exported model has no Belt for Blind root. Re-run export_web.py.');
  root.quaternion.identity();
  scene.add(gltf.scene);
  for (const [name, position] of Object.entries({ Left: [-125, 12, 72], Center: [0, 125, 72], Right: [125, 12, 72] })) {
    const beam = objects.get(`Live beam ${name}`);
    const motor = objects.get(`Motor ${name} body`);
    const rings = [0, 1, 2].map(k => objects.get(`Live motor ring ${name} ${k}`));
    if (!beam || !motor || rings.some(r => !r)) throw new Error(`Missing live objects for ${name}. Re-run export_web.py.`);
    beam.visible = false;
    eachMaterial(beam, material => { material.depthWrite = false; material.side = THREE.DoubleSide; });
    for (const ring of rings) {
      ring.visible = false;
      eachMaterial(ring, material => { material.depthWrite = false; });
    }
    const material = motor.material;
    motors.set(name, { object: motor, material, original: material.color.clone(), rings });
    sensors.set(name, { beam, length: null, label: makeLabel(name, position), card: $(`[data-sensor="${name}"]`) });
  }
}

function updateSensor(name, state, now, delta) {
  const view = sensors.get(name);
  const color = COLORS[state.zone];
  view.beam.visible = showBeams && state.length !== null;
  if (state.length !== null) {
    view.length = view.length === null ? state.length : THREE.MathUtils.lerp(view.length, state.length, 1 - Math.pow(0.7, delta / 0.05));
    view.beam.scale.setScalar(view.length);
  } else view.length = null;
  const pulse = reducedMotion.matches ? 0.5 : 0.5 + 0.5 * Math.sin(now * 12);
  eachMaterial(view.beam, material => {
    const cap = material.name.startsWith('Live obstacle');
    material.color.set(color); material.emissive.set(color);
    material.opacity = state.alert ? cap ? 0.95 : 0.2 + 0.35 * pulse : state.status === 'clear' ? 0.1 : cap ? 0.9 : 0.22;
    material.emissiveIntensity = state.alert ? cap ? 0.6 + 1.6 * pulse : 0.8 : cap ? 0.8 : 0.5;
  });
  view.label.update(state.label, color);
  // Labels are independent of the beam toggle and always show the real state.
  const card = view.card;
  card.style.setProperty('--accent', color);
  card.dataset.motor = state.motor;
  card.querySelector('.distance').textContent = state.cm ?? (state.status === 'clear' ? 'Clear' : '—');
  card.querySelector('.unit').hidden = state.cm === null;
  card.querySelector('.sensor-status').textContent = state.cm !== null ? state.alert ? `Alert · under ${ALERT_CM[name]} cm` : state.zone.replaceAll('-', ' ') : state.label === 'Waiting' ? 'Waiting for readings' : state.label;
  card.querySelector('.motor-status').textContent = state.motor ? 'Vibrating' : 'Motor off';
  const motor = motors.get(name);
  motor.material.color.copy(state.motor ? new THREE.Color('#ff2a2a') : motor.original);
  motor.material.emissive.set(state.motor ? '#ff2a2a' : '#000000');
  motor.material.emissiveIntensity = state.motor ? 0.8 + 1.6 * pulse : 0;
  motor.rings.forEach((ring, k) => {
    ring.visible = state.motor;
    const scale = reducedMotion.matches ? 1 + k * 0.7 : 1 + 2.2 * ((now * 2.2 + k / 3) % 1);
    ring.scale.set(scale, scale, 1);
  });
}

function updateStatus(live) {
  const imu = live ? snapshot.imu : null;
  const hasGravity = Boolean(imu?.found && Array.isArray(imu.gravity) && imu.gravity.length === 3 &&
    imu.gravity.every(Number.isFinite) && Math.hypot(...imu.gravity) >= 0.5);
  $('#set-level').disabled = !hasGravity;
  $('#imu-dot').classList.toggle('active', hasGravity);
  $('#tilt').textContent = imu?.found ? imu.tilt : '—';
  $('#motion').textContent = imu?.found ? `${imu.motion.toFixed(3)} g` : '— g';
  $('#wearer').textContent = !live ? 'Waiting' : snapshot.sitting ? 'Sitting · paused' : imu?.found ? imu.motion >= 0.08 ? 'Moving' : 'Active' : 'IMU missing';
  $('#calibration').textContent = !live ? 'Place the board flat and still for the first reading.' : !imu?.found ? 'IMU not found. Check the MPU6050 connection.' : !hasGravity ? 'No gravity readings. Upload the current firmware to enable live tilt.' : orientation.level ? 'Level is set. Tilt the real board to move the model.' : 'Hold the board still. Setting level…';
  connection.dataset.state = live ? 'live' : transportDown || !snapshot?.connected ? 'down' : 'waiting';
  connection.textContent = live ? snapshot.sitting ? 'Live · paused' : 'Live connection' : transportDown ? 'Server disconnected' : snapshot?.connected ? 'Waiting for readings' : 'ESP32 disconnected';
  liveDetail.textContent = live ? snapshot.sitting ? 'Wearer is sitting. Sensors and motors paused.' : `${snapshot.port || 'ESP32'} · receiving live readings` : transportDown ? 'Start the live-view server to reconnect.' : snapshot?.error || 'Connect the ESP32 by USB and close the Serial Monitor.';
}

$('#set-level').addEventListener('click', () => {
  if (!isLive(snapshot, receivedAt, performance.now() / 1000)) return;
  orientation.reset();
  orientation.update(snapshot.imu);
});
$('#sensor-turn').addEventListener('change', event => {
  orientation.turnSensorDeg = Number(event.target.value);
  orientation.reset();
});
$('#reset-view').addEventListener('click', resetView);
$('#beams').addEventListener('click', event => {
  showBeams = !showBeams;
  event.currentTarget.setAttribute('aria-pressed', showBeams);
});
$('#background').addEventListener('click', event => {
  showWorkshop = !showWorkshop;
  scene.background = showWorkshop && environment ? environment : studioColor;
  event.currentTarget.setAttribute('aria-pressed', showWorkshop);
  $('#environment-label').textContent = showWorkshop && environment ? 'ARTIST WORKSHOP' : 'STUDIO';
});
$('#fullscreen').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await $('.workspace').requestFullscreen();
  } catch { $('#fullscreen').textContent = 'Unavailable'; }
});
document.addEventListener('fullscreenchange', () => { $('#fullscreen').textContent = document.fullscreenElement ? 'Exit full screen' : 'Full screen'; });
renderer.domElement.addEventListener('webglcontextlost', event => {
  event.preventDefault();
  $('#loading').hidden = false;
  $('#loading-title').textContent = 'The graphics connection was interrupted';
  $('#loading-detail').textContent = 'Reload the page to reopen the 3D view.';
  $('.loader').hidden = true;
});

async function start() {
  const configResponse = await fetch('/assets/scene.json');
  if (!configResponse.ok) throw new Error('Missing scene metadata. Run 3d-model/export_web.py.');
  config = await configResponse.json();
  orientation = new BeltOrientation(config.turnSensorDeg);
  $('#sensor-turn').value = String(config.turnSensorDeg);
  resetView(); resize();
  // The HDRI is optional; missing it never prevents the model from loading.
  const environmentReady = new HDRLoader().loadAsync('/assets/workshop.hdr').then(texture => {
    texture.mapping = THREE.EquirectangularReflectionMapping;
    environment = texture;
    scene.environment = texture;
    scene.background = showWorkshop ? texture : studioColor;
    scene.backgroundBlurriness = 0.18;
    // Equirectangular maps use Y-up. Rotate the workshop into Blender's Z-up
    // world and apply the source world's 200-degree heading.
    scene.backgroundRotation.set(Math.PI / 2, 0, THREE.MathUtils.degToRad(config.environmentRotationDeg), 'ZYX');
    scene.environmentRotation.copy(scene.backgroundRotation);
    scene.remove(fallback);
    $('#environment-label').textContent = showWorkshop ? 'ARTIST WORKSHOP' : 'STUDIO';
  }).catch(() => { $('#environment-label').textContent = 'STUDIO · WORKSHOP HDRI NOT INSTALLED'; });

  const model = await new GLTFLoader().loadAsync('/assets/belt_for_blind.glb', progress => {
    if (progress.total) $('#loading-detail').textContent = `Loading model · ${Math.round(progress.loaded / progress.total * 100)}%`;
  });
  setupModel(model);
  $('#loading').hidden = true;
  // Open the real stream only after the model is ready, so calibration uses
  // the first visible live reading, exactly as Blender's Run Script does.
  const events = new EventSource('/events');
  events.onmessage = event => {
    snapshot = JSON.parse(event.data);
    receivedAt = performance.now() / 1000;
    transportDown = false;
    if (isLive(snapshot, receivedAt, receivedAt)) orientation.update(snapshot.imu);
  };
  events.onerror = () => { transportDown = true; snapshot = null; };
  window.addEventListener('pagehide', () => events.close(), { once: true });
  let lastTime = performance.now() / 1000;
  renderer.setAnimationLoop(timeMs => {
    const now = timeMs / 1000;
    const delta = Math.min(Math.max(now - lastTime, 0), 0.1);
    lastTime = now;
    const live = !transportDown && isLive(snapshot, receivedAt, now);
    if (live) orientation.apply(root.quaternion, delta);
    for (const name of SENSOR_NAMES) updateSensor(name, sensorState(snapshot, name, live), now, delta);
    updateStatus(live);
    controls.update();
    renderer.render(scene, camera);
  });
  await environmentReady;
}

await start();
