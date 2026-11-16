import * as THREE from './vendor/three/three.module.min.js';
export const clone = value => JSON.parse(JSON.stringify(value));
export function boardMatrix(layout) {
  return layout.mode === 'belt'
    ? new THREE.Matrix4().makeTranslation(0,-layout.belt.ry-8,0).multiply(new THREE.Matrix4().makeRotationX(Math.PI/2))
    : new THREE.Matrix4();
}
export function componentMatrix(c, layout) {
  const rotate = new THREE.Matrix4().makeRotationZ(THREE.MathUtils.degToRad(c.rotation));
  if (layout.mode === 'belt' && c.surface === 'belt') {
    const a = THREE.MathUtils.degToRad(c.angle), {rx,ry}=layout.belt;
    const normal = new THREE.Vector3(Math.sin(a)/rx,Math.cos(a)/ry,0).normalize();
    return new THREE.Matrix4().makeTranslation((rx+c.z)*Math.sin(a),(ry+c.z)*Math.cos(a),c.y)
      .multiply(new THREE.Matrix4().makeBasis(new THREE.Vector3(-normal.y,normal.x,0),new THREE.Vector3(0,0,1),normal)).multiply(rotate);
  }
  const local = new THREE.Matrix4().makeTranslation(c.x,c.y,c.z).multiply(rotate);
  return c.surface === 'board' ? boardMatrix(layout).multiply(local) : local;
}
export function pinPosition(endpoint, layout, types) {
  const c=layout.components.find(c=>c.id===endpoint.component);
  return new THREE.Vector3(...types[c.type].pins[endpoint.pin]).applyMatrix4(componentMatrix(c,layout));
}
export function wireCurve(w, layout, types) {
  const a=pinPosition(w.from,layout,types), b=pinPosition(w.to,layout,types);
  if (w.via) return new THREE.CatmullRomCurve3([a,new THREE.Vector3(...w.via),b],false,'centripetal');
  const cs=[w.from,w.to].map(e=>layout.components.find(c=>c.id===e.component));
  if (layout.mode==='belt' && cs.some(c=>c.surface==='belt')) {
    const {rx,ry}=layout.belt;
    const start=Math.atan2(a.x/rx,a.y/ry), end=Math.atan2(b.x/rx,b.y/ry);
    const delta=Math.atan2(Math.sin(end-start),Math.cos(end-start));
    // Radius includes the endpoints' stand-off so wires stay outside the strap.
    const clearance=Math.max(20,...cs.map(c=>c.z))+w.slack;
    const pts=[a];
    for(let i=0;i<=24;i++) {
      const t=i/24,angle=start+delta*t;
      pts.push(new THREE.Vector3((rx+clearance)*Math.sin(angle),(ry+clearance)*Math.cos(angle),a.z*(1-t)+b.z*t));
    }
    pts.push(b);
    return new THREE.CatmullRomCurve3(pts,false,'centripetal');
  }
  const lift=layout.mode==='belt' && cs.every(c=>c.surface==='board') ? new THREE.Vector3(0,-1,0) : new THREE.Vector3(0,0,1);
  return new THREE.CatmullRomCurve3([a,a.clone().lerp(b,.25).addScaledVector(lift,w.slack+4),a.clone().lerp(b,.75).addScaledVector(lift,w.slack+4),b],false,'centripetal');
}
export function validateLayout(value, types, mode) {
  const fail=message=>{throw new Error(message);};
  if(!value || value.version!==1 || value.mode!==mode) fail('Choose a version 1 '+mode+' layout.');
  if(!Array.isArray(value.components)||value.components.length>150||!Array.isArray(value.wires)||value.wires.length>500) fail('Invalid component or wire list.');
  const finite=n=>typeof n==='number' && Number.isFinite(n) && Math.abs(n)<=1e6;
  if(!value.belt || !['rx','ry','width'].every(k=>finite(value.belt[k])&&value.belt[k]>=10&&value.belt[k]<=2000)) fail('Invalid belt dimensions.');
  const ids=new Set(), wireIds=new Set();
  for(const c of value.components) {
    if(typeof c.id!=='string'||ids.has(c.id)||!Object.hasOwn(types,c.type)||['vero','belt'].includes(c.type)||typeof c.label!=='string'||c.label.length>120) fail('Invalid or duplicate component.');
    if(!['x','y','z','rotation','angle'].every(k=>finite(c[k]))||!['board','belt','free'].includes(c.surface)||(mode==='vero'&&c.surface==='belt')) fail('Invalid component position.');
    ids.add(c.id);
  }
  for(const w of value.wires) {
    if(typeof w.id!=='string'||wireIds.has(w.id)||!/^#[0-9a-f]{6}$/i.test(w.color)||!finite(w.slack)||w.slack<0) fail('Invalid wire.');
    wireIds.add(w.id);
    for(const e of [w.from,w.to]) {
      const c=value.components.find(c=>c.id===e?.component);
      if(!c||!Object.hasOwn(types[c.type].pins,e.pin)) fail('A wire references a missing pin.');
    }
    if(w.from.component===w.to.component&&w.from.pin===w.to.pin) fail('A wire needs two different pins.');
    if(w.via!==null&&(!Array.isArray(w.via)||w.via.length!==3||!w.via.every(finite))) fail('Invalid wire bend.');
  }
  return clone(value);
}
export function connect(layout,from,to,color='#438bd1') {
  if(from.component===to.component && from.pin===to.pin) throw new Error('Choose a different destination pin.');
  const key=e=>e.component+'\0'+e.pin;
  if(layout.wires.some(w=>[key(w.from),key(w.to)].sort().join('|')===[key(from),key(to)].sort().join('|'))) throw new Error('These pins are already connected.');
  const w={id:globalThis.crypto.randomUUID(),from:clone(from),to:clone(to),color,slack:7,via:null};
  layout.wires.push(w); return w;
}
