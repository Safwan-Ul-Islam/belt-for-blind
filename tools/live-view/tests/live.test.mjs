import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Quaternion, Vector3 } from '../vendor/three/three.core.min.js';
import { BeltOrientation } from '../orientation.js';
import { isLive, sensorState } from '../live-state.js';

const imu = gravity => ({ found: true, gravity });
const close = (a, b, epsilon = 1e-7) => assert.ok(Math.abs(a - b) < epsilon, `${a} != ${b}`);

test('flat then 30° tilt matches Blender’s shortest-arc quaternion', () => {
  const orientation = new BeltOrientation();
  orientation.update(imu([0, 0, 1]));
  close(orientation.target.angleTo(new Quaternion()), 0);
  orientation.update(imu([0.5, 0, Math.sqrt(0.75)]));
  close(orientation.target.x, 0);
  close(orientation.target.y, -Math.sin(Math.PI / 12));
  close(orientation.target.z, 0);
  close(orientation.target.w, Math.cos(Math.PI / 12));
});

test('all six mounting faces and four heading corrections preserve Blender axes', () => {
  for (let axis = 0; axis < 3; axis++) for (const sign of [-1, 1]) for (const turn of [0, 90, 180, 270]) {
    const level = [0, 0, 0]; level[axis] = sign;
    const gravity = [...level]; gravity[axis] *= Math.sqrt(.75); gravity[(axis + 1) % 3] = .5;
    const orientation = new BeltOrientation(turn);
    assert.equal(orientation.update(imu(level)), true);
    orientation.update(imu(gravity));
    const mapped = new Vector3(...gravity).applyMatrix4(orientation.mapping).applyQuaternion(orientation.target);
    close(mapped.distanceTo(new Vector3(0, 0, 1)), 0);
    close(orientation.mapping.determinant(), 1);
    close(orientation.target.angleTo(new Quaternion()), Math.PI / 6);
  }
});

test('a tilted initial reference and Set level recalibration behave like Blender', () => {
  const orientation = new BeltOrientation();
  orientation.update(imu([.2, .1, .97]));
  close(orientation.target.angleTo(new Quaternion()), 0);
  orientation.update(imu([.5, .1, .86]));
  assert.ok(orientation.target.angleTo(new Quaternion()) > .2);
  orientation.reset(); orientation.update(imu([.5, .1, .86]));
  close(orientation.target.angleTo(new Quaternion()), 0);
});

test('invalid or absent gravity does not recalibrate or move the model', () => {
  const orientation = new BeltOrientation();
  for (const data of [null, { found: false, gravity: [0, 0, 1] }, imu(null), imu([0, 0, 0]), imu([NaN, 0, 1]), imu([0, 1])]) {
    assert.equal(orientation.update(data), false);
    assert.equal(orientation.level, null);
  }
});

test('smoothing matches Blender at 20 Hz and remains the same at 60 Hz', () => {
  const orientation = new BeltOrientation();
  orientation.update(imu([0, 0, 1])); orientation.update(imu([.5, 0, Math.sqrt(.75)]));
  const at20 = new Quaternion(), at60 = new Quaternion();
  orientation.apply(at20, .05);
  close(at20.angleTo(orientation.target), Math.PI / 6 * .75);
  for (let i = 1; i < 10; i++) orientation.apply(at20, .05);
  for (let i = 0; i < 30; i++) orientation.apply(at60, 1 / 60);
  close(at20.angleTo(at60), 0);
});

test('live state expires when events stop, even with a connected USB snapshot', () => {
  const snapshot = { connected: true, age: 1 };
  assert.equal(isLive(snapshot, 10, 11.9), true);
  assert.equal(isLive(snapshot, 10, 12), false);
  for (const age of [null, undefined, NaN, -1, 3, 5]) assert.equal(isLive({ connected: true, age }, 0, 0), false);
  assert.equal(isLive({ connected: false, age: 0 }, 0, 0), false);
});

test('distance scaling, per-side alerts and actual motor outputs use live data', () => {
  const snapshot = { sensors: { Left: { status: 'ok', cm: 20 }, Center: { status: 'ok', cm: 20 }, Right: { status: 'ok', cm: 250 } }, motors: { Center: true } };
  const left = sensorState(snapshot, 'Left', true), center = sensorState(snapshot, 'Center', true), right = sensorState(snapshot, 'Right', true);
  assert.equal(left.alert, false); assert.equal(center.alert, true);
  assert.equal(center.motor, true); assert.equal(left.motor, false);
  assert.equal(center.length, 200); assert.equal(right.length, 2000); assert.equal(right.label, '250 cm');
});

test('pause, disconnect, clear and missing sensor data disable the appropriate effects', () => {
  const snapshot = { sensors: { Left: { status: 'clear' }, Center: { status: 'nosignal' } }, motors: { Left: true } };
  assert.equal(sensorState(snapshot, 'Left', true).length, 300);
  assert.equal(sensorState(snapshot, 'Center', true).length, null);
  assert.equal(sensorState(snapshot, 'Right', true).label, 'Waiting');
  const paused = sensorState({ ...snapshot, sitting: true }, 'Left', true);
  assert.equal(paused.motor, false); assert.equal(paused.label, 'Paused'); assert.equal(paused.length, null);
  const offline = sensorState(snapshot, 'Left', false);
  assert.equal(offline.motor, false); assert.equal(offline.length, null);
  assert.equal(sensorState(null, 'Left', false).label, 'Waiting');
});
