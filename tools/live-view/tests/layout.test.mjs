import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {clone, componentMatrix, pinPosition, wireCurve, validateLayout, connect} from '../layout-model.js';
const manifest=JSON.parse(fs.readFileSync(new URL('../assets/customizer.json',import.meta.url)));
const {types,defaults}=manifest;
test('both complete default circuits have valid endpoints and preserve firmware pin mapping',()=>{
 for(const mode of ['vero','belt']){
  const l=validateLayout(defaults[mode],types,mode);assert.equal(l.components.length,26);assert.equal(l.wires.length,52);
  for(const [side,trig,echo] of [['left','D25','D34'],['center','D26','D35'],['right','D27','D32']]){
   assert.ok(l.wires.some(w=>w.from.component==='esp'&&w.from.pin===trig&&w.to.component==='sensor-'+side&&w.to.pin==='Trig'));
   assert.ok(l.wires.some(w=>w.from.component==='r1k-'+side&&w.from.pin==='B'&&w.to.component==='esp'&&w.to.pin===echo));
  }
 }
});
test('wire endpoints follow translation and rotation; length has no fixed cap',()=>{
 const l=clone(defaults.vero), w=l.wires[0], c=l.components.find(c=>c.id===w.to.component);
 const initial=wireCurve(w,l,types).getLength();c.x+=10000;c.rotation=137;
 const curve=wireCurve(w,l,types);
 assert.ok(curve.getLength()>initial+9000);
 assert.ok(curve.getPoint(0).distanceTo(pinPosition(w.from,l,types))<1e-6);
 assert.ok(curve.getPoint(1).distanceTo(pinPosition(w.to,l,types))<1e-6);
});
test('belt mounts face outward and wires route around the exterior',()=>{
 const l=clone(defaults.belt),w=l.wires.find(w=>w.to.component==='sensor-center');
 const curve=wireCurve(w,l,types);
 for(let i=5;i<=95;i++){
  const p=curve.getPoint(i/100),r=(p.x/l.belt.rx)**2+(p.y/l.belt.ry)**2;
  assert.ok(r>=.98,'wire should not cut through the wearer');
 }
 const c=l.components.find(c=>c.id==='sensor-center');c.angle=90;
 const m=componentMatrix(c,l);assert.ok(Math.abs(m.determinant()-1)<1e-8,"mounting must not mirror component pins");assert.ok(m.elements[12]>l.belt.rx);assert.ok(Math.abs(m.elements[13])<1e-8);
});
test('custom bends, serialization and connection removal preserve meaningful state',()=>{
 const l=clone(defaults.belt),w=l.wires[0];w.via=[230,-200,70];
 const loaded=validateLayout(JSON.parse(JSON.stringify(l)),types,'belt');
 assert.deepEqual(loaded,l);assert.ok(wireCurve(w,l,types).getLength()>0);
 const custom=connect(l,{component:'esp',pin:'D2'},{component:'imu',pin:'INT'});
 assert.ok(l.wires.includes(custom));
 assert.throws(()=>connect(l,custom.to,custom.from),/already connected/);
 assert.throws(()=>connect(l,custom.from,custom.from),/different/);
});
test('invalid imports are rejected without changing the current layout',()=>{
 for(const mutate of [l=>l.components[0].x=Infinity,l=>l.components[1].id=l.components[0].id,l=>l.wires[0].to.pin='missing',l=>l.wires[0].via=[1,2],l=>l.wires[0].color='bad',l=>l.belt.rx=0]){
  const l=clone(defaults.vero);mutate(l);assert.throws(()=>validateLayout(l,types,'vero'));
 }
 assert.throws(()=>validateLayout(defaults.belt,types,'vero'));
});


test('the actual Blender library contains every independent component at millimetre scale',async()=>{
 const {GLTFLoader}=await import('../vendor/three/addons/loaders/GLTFLoader.js');
 const {Box3,Vector3}=await import('../vendor/three/three.core.min.js');
 const bytes=fs.readFileSync(new URL('../assets/customizer.glb',import.meta.url));
 const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
 const roots=new Map();gltf.scene.traverse(o=>{if(o.userData.component_type)roots.set(o.userData.component_type,o);});
 assert.deepEqual([...roots.keys()].sort(),Object.keys(types).sort());
 for(const [key,obj] of roots){
  assert.ok(obj.children.length,key+' must contain real Blender geometry');
  assert.ok(obj.position.length()<1e-6,key+' must be centred for mounting');
 }
 const size=new Box3().setFromObject(roots.get('vero')).getSize(new Vector3());
 assert.ok(Math.abs(size.x-180)<.1);assert.ok(Math.abs(size.y-120)<.1);
 const sensor=new Box3().setFromObject(roots.get('sensor')).getSize(new Vector3());
 assert.ok(sensor.x>44&&sensor.x<46);assert.ok(sensor.z<22,'sensor must face outward from its mounting surface');
});
