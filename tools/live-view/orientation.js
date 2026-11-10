import { Matrix4, Quaternion, Vector3 } from './vendor/three/three.core.min.js';

// Same coordinate mapping and shortest-arc rotation as live_link.py.
// The GLB deliberately retains Blender's Z-up axes.
export class BeltOrientation {
  constructor(turnSensorDeg = 0) {
    this.turnSensorDeg = turnSensorDeg;
    this.reset();
  }

  reset() {
    this.level = null;
    this.mapping = null;
    this.target = new Quaternion();
  }

  update(imu) {
    const values = imu?.found && imu.gravity;
    if (!Array.isArray(values) || values.length !== 3 || !values.every(Number.isFinite)) return false;
    const gravity = new Vector3(...values);
    if (gravity.length() < 0.5) return false;
    gravity.normalize();
    if (!this.level) {
      this.level = gravity.clone();
      const k = values.reduce((best, value, i) => Math.abs(value) > Math.abs(values[best]) ? i : best, 0);
      const sign = values[k] > 0 ? 1 : -1;
      const axes = [];
      axes[k] = new Vector3(0, 0, sign);
      axes[(k + 1) % 3] = new Vector3(1, 0, 0);
      axes[(k + 2) % 3] = new Vector3(0, sign, 0);
      this.mapping = new Matrix4().makeRotationZ(this.turnSensorDeg * Math.PI / 180)
        .multiply(new Matrix4().makeBasis(...axes));
    }
    const from = gravity.applyMatrix4(this.mapping);
    const to = this.level.clone().applyMatrix4(this.mapping);
    this.target.setFromUnitVectors(from, to);
    return true;
  }

  apply(quaternion, deltaSeconds) {
    // Blender ticks every 50 ms and slerps by .25; keep the same response at
    // any browser frame rate, including after a tab has been in the background.
    const amount = 1 - Math.pow(0.75, Math.min(deltaSeconds, 0.1) / 0.05);
    if (quaternion.angleTo(this.target) > Math.PI / 3600) quaternion.slerp(this.target, amount);
  }
}
