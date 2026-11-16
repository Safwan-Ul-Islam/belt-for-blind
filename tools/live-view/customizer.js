import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone, boardMatrix, componentMatrix, pinPosition, wireCurve, validateLayout, connect } from './layout-model.js';
const $=s=>document.querySelector(s);
const mode=location.pathname.startsWith('/belt')?'belt':'vero';
const storageKey='belt-design-v1-'+mode;
$('#nav-'+mode).classList.add('nav-current');
$('#page-title').textContent=mode==='belt'?'Around the belt.':'On the vero board.';
document.title='Belt for Blind · '+(mode==='belt'?'Belt studio':'Vero board');
$('#belt-settings').hidden=mode!=='belt';
if(mode==='vero') $('#surface option[value=belt]').remove();
const response=await fetch('/assets/customizer.json');
if(!response.ok) throw new Error('Missing component catalogue. Run build_customizer.py.');
const manifest=await response.json(), types=manifest.types;
let layout=clone(manifest.defaults[mode]);
let storageProblem='';
try { const saved=localStorage.getItem(storageKey); if(saved) layout=validateLayout(JSON.parse(saved),types,mode); }
catch { storageProblem='Saved layout could not be read. The default is open; import a backup if needed.'; }
let selected=null, tool='move', pendingPin=null, drag=null;
const past=[], future=[];
const viewport=$('#editor-viewport'), scene=new THREE.Scene();
scene.background=new THREE.Color('#dce3d9');
const camera=new THREE.PerspectiveCamera(40,1,.1,100000);
camera.up.set(0,0,1);
const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.3;
viewport.append(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true; controls.minDistance=15; controls.maxDistance=100000;
scene.add(new THREE.HemisphereLight(0xffffff,0x7a8c72,2.5));
for(const [pos,intensity] of [[[100,-150,350],3], [[-200,100,100],2]]) {
  const light=new THREE.DirectionalLight(0xffffff,intensity); light.position.set(...pos); scene.add(light);
}
const grid=new THREE.GridHelper(mode==='belt'?800:500,mode==='belt'?40:50,0x9aa99a,0xc5cfbf);
grid.rotation.x=Math.PI/2; grid.position.z=mode==='belt'?-42:-6; grid.material.transparent=true; grid.material.opacity=.5; scene.add(grid);
const hardware=new THREE.Group(), wireGroup=new THREE.Group(), pinGroup=new THREE.Group();
scene.add(hardware,wireGroup,pinGroup);
const prototypes={}, objects=new Map(), labels=new Map(), wireObjects=new Map();
const gltf=await new GLTFLoader().loadAsync('/assets/customizer.glb');
gltf.scene.traverse(o=>{if(o.userData.component_type) prototypes[o.userData.component_type]=o;});
for(const key of Object.keys(types)) if(!prototypes[key]) throw new Error('Missing Blender part: '+key);
const pinGeometry=new THREE.SphereGeometry(.85,10,8);
const pinMaterial=new THREE.MeshBasicMaterial({color:0xf3c45f,depthTest:false});
const handle=new THREE.Mesh(new THREE.SphereGeometry(2.3,16,12),new THREE.MeshBasicMaterial({color:0xd78027,depthTest:false}));
handle.renderOrder=30;handle.visible=false;scene.add(handle);
const selectionBox=new THREE.BoxHelper(new THREE.Object3D(),0x4d8760);selectionBox.visible=false;scene.add(selectionBox);
function message(text){$('#message').textContent=text;}
function persist(){
  try{localStorage.setItem(storageKey,JSON.stringify(layout));$('#save-state').textContent='Saved in browser';}
  catch{$('#save-state').textContent='Export to save';message('Browser storage is unavailable or full. Use Export JSON to save this layout.');}
}
function historyButtons(){$('#undo').disabled=!past.length;$('#redo').disabled=!future.length;}
function mutate(fn){const previous=clone(layout);try{fn();validateLayout(layout,types,mode);past.push(previous);if(past.length>60)past.shift();future.length=0;rebuild();persist();}catch(e){layout=previous;message(e.message);}historyButtons();}
function model(type){const obj=prototypes[type].clone(true);obj.position.set(0,0,0);obj.rotation.set(0,0,0);obj.scale.set(1,1,1);return obj;}
function updateTransforms(){
  for(const c of layout.components){const obj=objects.get(c.id);obj.matrix.copy(componentMatrix(c,layout));obj.matrixWorldNeedsUpdate=true;}
  hardware.updateMatrixWorld(true);updateWires();updateSelectionBox();
}
function rebuild(){
  hardware.clear();pinGroup.clear();objects.clear();labels.clear();$('#labels').replaceChildren();
  const board=model('vero');board.matrixAutoUpdate=false;board.matrix.copy(boardMatrix(layout));hardware.add(board);
  if(mode==='belt'){const belt=model('belt');belt.scale.set(layout.belt.rx/170,layout.belt.ry/135,layout.belt.width/50);hardware.add(belt);}
  for(const c of layout.components){
    const obj=model(c.type);obj.matrixAutoUpdate=false;obj.userData.componentId=c.id;
    obj.traverse(child=>child.userData.componentId=c.id);hardware.add(obj);objects.set(c.id,obj);
    const label=document.createElement('span');label.className='part-label';label.textContent=c.label;$('#labels').append(label);labels.set(c.id,label);
  }
  if(selected?.kind==='component'&&!objects.has(selected.id)||selected?.kind==='wire'&&!layout.wires.some(w=>w.id===selected.id))selected=null;
  updateTransforms();renderLists();inspect();updatePins();
  for(const key of ['rx','ry','width'])$('#belt-'+key).value=layout.belt[key];
}
function updateWires(){
  for(const obj of wireGroup.children){obj.geometry.dispose();obj.material.dispose();}
  wireGroup.clear();wireObjects.clear();let total=0;
  for(const w of layout.wires){
    const curve=wireCurve(w,layout,types), length=curve.getLength();total+=length;
    const isSelected=selected?.kind==='wire'&&selected.id===w.id;
    const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,mode==='belt'?72:32,isSelected?.8:.45,6,false),new THREE.MeshStandardMaterial({color:w.color,roughness:.5,emissive:isSelected?w.color:0,emissiveIntensity:.25}));
    mesh.userData.wireId=w.id;mesh.userData.length=length;mesh.userData.curve=curve;wireGroup.add(mesh);wireObjects.set(w.id,mesh);
  }
  wireGroup.visible=$('#show-wires').checked;
  $('#wire-total').textContent=layout.wires.length+' wires · '+(total/1000).toFixed(2)+' m';
  handle.visible=selected?.kind==='wire'&&wireGroup.visible;
  if(handle.visible){const obj=wireObjects.get(selected.id);if(obj)handle.position.copy(obj.userData.curve.getPoint(.5));else handle.visible=false;}
}
function select(kind,id){selected=kind?{kind,id}:null;inspect();renderLists();updateWires();updateSelectionBox();updatePins();}
function updateSelectionBox(){selectionBox.visible=selected?.kind==='component';if(selectionBox.visible&&objects.has(selected.id))selectionBox.setFromObject(objects.get(selected.id));}
function option(value,label){const o=document.createElement('option');o.value=value;o.textContent=label;return o;}
function populatePins(prefix){const c=layout.components.find(c=>c.id===$('#'+prefix+'-component').value);$('#'+prefix+'-pin').replaceChildren(...Object.keys(c?types[c.type].pins:{}).map(p=>option(p,p)));}
function renderLists(){
  $('#part-count').textContent=layout.components.length;
  $('#component-list').replaceChildren(...layout.components.map(c=>{
    const btn=document.createElement('button');btn.setAttribute('aria-pressed',selected?.kind==='component'&&selected.id===c.id?'true':'false');
    const icon=document.createElement('span');icon.className='part-icon';icon.textContent=c.type==='sensor'?'◉':c.type==='motor'?'●':c.type.startsWith('r')?'∿':'▣';
    const title=document.createElement('span');title.textContent=c.label;const small=document.createElement('small');small.textContent=c.surface==='belt'?'Belt · '+Math.round(c.angle)+'°':c.surface==='board'?'Vero board':'Free space';title.append(small);btn.append(icon,title);btn.onclick=()=>select('component',c.id);return btn;
  }));
  for(const prefix of ['from','to']){
    const field=$('#'+prefix+'-component'),value=field.value,pin=$('#'+prefix+'-pin').value;
    field.replaceChildren(...layout.components.map(c=>option(c.id,c.label)));
    if(layout.components.some(c=>c.id===value))field.value=value;
    else if(prefix==='to'&&layout.components.length>1)field.selectedIndex=1;
    populatePins(prefix);if([...$('#'+prefix+'-pin').options].some(o=>o.value===pin))$('#'+prefix+'-pin').value=pin;
  }
  $('#connection-count').textContent='('+layout.wires.length+')';
  $('#connections').replaceChildren(...layout.wires.map(w=>{const btn=document.createElement('button'),swatch=document.createElement('i'),text=document.createElement('span'),length=document.createElement('small');swatch.style.background=w.color;text.textContent=endpointName(w.from)+' → '+endpointName(w.to);length.textContent=Math.round(wireObjects.get(w.id)?.userData.length||0)+' mm';btn.append(swatch,text,length);btn.onclick=()=>select('wire',w.id);return btn;}));
}
function endpointName(e){return (layout.components.find(c=>c.id===e.component)?.label||e.component)+' · '+e.pin;}
function inspect(){
  const c=selected?.kind==='component'?layout.components.find(c=>c.id===selected.id):null;
  const w=selected?.kind==='wire'?layout.wires.find(w=>w.id===selected.id):null;
  $('#empty-selection').hidden=!!selected;$('#component-inspector').hidden=!c;$('#wire-inspector').hidden=!w;$('#selection-kind').textContent=c?'COMPONENT':w?'WIRE':'LAYOUT';
  if(c){
    $('#selected-name').textContent=c.label;$('#surface').value=c.surface;
    const belt=c.surface==='belt';$('#x-label').firstChild.textContent=belt?'Angle · °':'X · mm';$('#y-label').firstChild.textContent=belt?'Height · mm':'Y · mm';
    $('#pos-x').value=+(belt?c.angle:c.x).toFixed(2);$('#pos-y').value=+c.y.toFixed(2);$('#pos-z').value=+c.z.toFixed(2);$('#rotation').value=c.rotation;
    $('#pin-list').replaceChildren(...Object.keys(types[c.type].pins).map(pin=>{const btn=document.createElement('button');btn.textContent=pin;btn.title='Connect '+pin;btn.onclick=()=>{setTool('wire');choosePin({component:c.id,pin});};return btn;}));
  }
  if(w){
    $('#wire-endpoints').textContent=endpointName(w.from)+' → '+endpointName(w.to);
    $('#wire-length').textContent=(wireObjects.get(w.id)?.userData.length||0).toFixed(1)+' mm';
    $('#wire-color').value=w.color;$('#wire-slack').value=w.slack;
    const p=w.via||wireCurve(w,layout,types).getPoint(.5).toArray();['x','y','z'].forEach((k,i)=>$('#bend-'+k).value=+p[i].toFixed(2));
  }
  for(const [id,label] of labels)label.classList.toggle('selected',c?.id===id);
}
function updatePins(){
  pinGroup.clear();
  for(const c of layout.components){
    if(tool!=='wire'&&!(selected?.kind==='component'&&selected.id===c.id))continue;
    for(const pin of Object.keys(types[c.type].pins)){const marker=new THREE.Mesh(pinGeometry,pinMaterial);marker.position.copy(pinPosition({component:c.id,pin},layout,types));marker.userData.endpoint={component:c.id,pin};marker.renderOrder=20;pinGroup.add(marker);}
  }
}
function setTool(next){tool=next;pendingPin=null;$('#wire-prompt').textContent='Wire mode: প্রথম পিন, তারপর দ্বিতীয় পিন বেছে নিন।';document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.mode===tool));viewport.style.cursor=tool==='wire'?'crosshair':tool==='move'?'grab':'default';updatePins();}
function choosePin(endpoint){
  if(!pendingPin){pendingPin=clone(endpoint);$('#wire-prompt').textContent='From '+endpointName(endpoint)+' — এবার গন্তব্য পিন বেছে নিন।';message($('#wire-prompt').textContent);return;}
  const from=clone(pendingPin);mutate(()=>{const w=connect(layout,from,endpoint);selected={kind:'wire',id:w.id};});pendingPin=null;$('#wire-prompt').textContent='Choose the first pin for another wire.';
}
function fit(top=false){
  const box=new THREE.Box3().setFromObject(hardware),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
  const dist=Math.max(size.x,size.y,size.z,80)/Math.tan(THREE.MathUtils.degToRad(camera.fov/2))/Math.min(camera.aspect,1)*.9;
  controls.target.copy(center);camera.position.copy(center).addScaledVector(top?new THREE.Vector3(0,-.001,1):new THREE.Vector3(.25,-.7,1).normalize(),dist);camera.lookAt(center);controls.update();
}
const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();
function ray(event){const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);}
function hit(objects,recursive=true){return raycaster.intersectObjects(objects,recursive)[0];}
const canvas=renderer.domElement;
canvas.addEventListener('pointerdown',event=>{
  if(event.button!==0||tool==='orbit')return;
  ray(event);const pinHit=tool==='wire'?hit(pinGroup.children):null;
  if(pinHit){event.stopImmediatePropagation();choosePin(pinHit.object.userData.endpoint);return;}
  const handleHit=handle.visible?hit([handle]):null;
  const componentHit=hit(hardware.children),wireHit=wireGroup.visible?hit(wireGroup.children):null;
  const cId=componentHit?.object.userData.componentId;
  if(handleHit){
    const normal=camera.getWorldDirection(new THREE.Vector3());const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(normal,handle.position);
    drag={kind:'wire',id:selected.id,plane,before:clone(layout),pointer:event.pointerId};
  }else if(cId&&tool==='move'){
    select('component',cId);const c=layout.components.find(c=>c.id===cId),obj=objects.get(cId),origin=new THREE.Vector3().setFromMatrixPosition(obj.matrixWorld);
    const normal=new THREE.Vector3(0,0,1).transformDirection(c.surface==='board'?boardMatrix(layout):c.surface==='belt'?componentMatrix(c,layout):new THREE.Matrix4());
    const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(normal,origin),start=raycaster.ray.intersectPlane(plane,new THREE.Vector3());
    if(!start)return;
    drag={kind:'component',id:cId,plane,start,original:clone(c),before:clone(layout),pointer:event.pointerId};
  }else if(wireHit && (!componentHit || wireHit.distance<componentHit.distance+1)){
    select('wire',wireHit.object.userData.wireId);event.stopImmediatePropagation();return;
  }else if(cId){select('component',cId);event.stopImmediatePropagation();return;}
  else return;
  controls.enabled=false;canvas.setPointerCapture(event.pointerId);event.stopImmediatePropagation();
},true);
canvas.addEventListener('pointermove',event=>{
  ray(event);
  if(!drag){
    const p=tool==='wire'?hit(pinGroup.children):null;$('#pin-tooltip').hidden=!p;
    if(p){const rect=viewport.getBoundingClientRect();$('#pin-tooltip').textContent=endpointName(p.object.userData.endpoint);$('#pin-tooltip').style.left=Math.min(event.clientX-rect.left+12,rect.width-160)+'px';$('#pin-tooltip').style.top=(event.clientY-rect.top+12)+'px';}return;
  }
  const point=raycaster.ray.intersectPlane(drag.plane,new THREE.Vector3());if(!point)return;
  if(drag.kind==='wire')layout.wires.find(w=>w.id===drag.id).via=point.toArray();
  else{
    const c=layout.components.find(c=>c.id===drag.id),o=drag.original;
    if(c.surface==='belt'){
      const dx=raycaster.ray.direction.x/layout.belt.rx,dy=raycaster.ray.direction.y/layout.belt.ry,ox=raycaster.ray.origin.x/layout.belt.rx,oy=raycaster.ray.origin.y/layout.belt.ry;
      const aa=dx*dx+dy*dy,bb=2*(dx*ox+dy*oy),cc=ox*ox+oy*oy-1,disc=bb*bb-4*aa*cc;
      let p=point;
      if(disc>=0&&aa>1e-10){const candidates=[(-bb-Math.sqrt(disc))/(2*aa),(-bb+Math.sqrt(disc))/(2*aa)].filter(t=>t>0).map(t=>raycaster.ray.at(t,new THREE.Vector3()));
        candidates.sort((a,b)=>{const delta=v=>Math.abs(Math.atan2(Math.sin(Math.atan2(v.x/layout.belt.rx,v.y/layout.belt.ry)-THREE.MathUtils.degToRad(c.angle)),Math.cos(Math.atan2(v.x/layout.belt.rx,v.y/layout.belt.ry)-THREE.MathUtils.degToRad(c.angle))));return delta(a)-delta(b);});if(candidates[0])p=candidates[0];}
      c.angle=THREE.MathUtils.radToDeg(Math.atan2(p.x/layout.belt.rx,p.y/layout.belt.ry));c.y=Math.max(-layout.belt.width/2,Math.min(layout.belt.width/2,p.z));
    }else{
      const inv=c.surface==='board'?boardMatrix(layout).invert():new THREE.Matrix4();
      const delta=point.clone().applyMatrix4(inv).sub(drag.start.clone().applyMatrix4(inv));
      const snap=n=>$('#snap').checked?Math.round(n/2.54)*2.54:n;
      c.x=snap(o.x+delta.x);c.y=snap(o.y+delta.y);
    }
  }
  updateTransforms();updatePins();inspect();
});
function finishDrag(cancel=false){if(!drag)return;const before=drag.before,pointerId=drag.pointer;drag=null;controls.enabled=true;if(canvas.hasPointerCapture(pointerId))canvas.releasePointerCapture(pointerId);if(cancel)layout=before;else if(JSON.stringify(before)!==JSON.stringify(layout)){past.push(before);if(past.length>60)past.shift();future.length=0;persist();}rebuild();historyButtons();}
canvas.addEventListener('pointerup',()=>finishDrag());canvas.addEventListener('pointercancel',()=>finishDrag(true));canvas.addEventListener('lostpointercapture',()=>{if(drag)finishDrag(true);});
canvas.addEventListener('pointerleave',()=>$('#pin-tooltip').hidden=true);
document.querySelectorAll('[data-mode]').forEach(btn=>btn.onclick=()=>setTool(btn.dataset.mode));
$('#fit').onclick=()=>fit();$('#top').onclick=()=>fit(true);
$('#show-wires').onchange=()=>{wireGroup.visible=$('#show-wires').checked;handle.visible=wireGroup.visible&&selected?.kind==='wire';};
$('#show-labels').onchange=()=>$('#labels').hidden=!$('#show-labels').checked;
$('#surface').onchange=()=>{const c=layout.components.find(c=>c.id===selected?.id);if(!c)return;mutate(()=>{c.surface=$('#surface').value;if(c.surface==='belt'){c.angle=0;c.y=0;c.z=5;}});};
$('#apply-position').onclick=()=>mutate(()=>{const c=layout.components.find(c=>c.id===selected?.id);c[c.surface==='belt'?'angle':'x']=number('#pos-x');c.y=number('#pos-y');c.z=number('#pos-z');c.rotation=number('#rotation');});
function number(selector){if($(selector).value.trim()==='')throw new Error('Enter a number in each field.');const value=Number($(selector).value);if(!Number.isFinite(value))throw new Error('Enter a finite number.');return value;}
function removeSelection(){if(!selected)return;mutate(()=>{if(selected.kind==='component'){layout.components=layout.components.filter(c=>c.id!==selected.id);layout.wires=layout.wires.filter(w=>w.from.component!==selected.id&&w.to.component!==selected.id);}else layout.wires=layout.wires.filter(w=>w.id!==selected.id);selected=null;pendingPin=null;});}
$('#remove-component').onclick=removeSelection;$('#remove-wire').onclick=removeSelection;
$('#apply-wire').onclick=()=>mutate(()=>{const w=layout.wires.find(w=>w.id===selected?.id);w.color=$('#wire-color').value;w.slack=number('#wire-slack');});
$('#apply-bend').onclick=()=>mutate(()=>{layout.wires.find(w=>w.id===selected?.id).via=['x','y','z'].map(k=>number('#bend-'+k));});
$('#auto-route').onclick=()=>mutate(()=>{layout.wires.find(w=>w.id===selected?.id).via=null;});
for(const prefix of ['from','to'])$('#'+prefix+'-component').onchange=()=>populatePins(prefix);
$('#connect').onclick=()=>mutate(()=>{const e=prefix=>({component:$('#'+prefix+'-component').value,pin:$('#'+prefix+'-pin').value});if(!e('from').pin||!e('to').pin)throw new Error('Add components with pins first.');const w=connect(layout,e('from'),e('to'));selected={kind:'wire',id:w.id};message('Wire connected. It will follow both pins as you move them.');});
$('#add-type').replaceChildren(...Object.keys(types).filter(t=>!['vero','belt'].includes(t)).map(t=>option(t,types[t].label)));
$('#add-component').onclick=()=>mutate(()=>{if(layout.components.length>=150)throw new Error('This layout supports up to 150 components.');const type=$('#add-type').value,id=crypto.randomUUID();layout.components.push({id,type,label:types[type].label+' '+(layout.components.length+1),x:0,y:0,z:4,rotation:0,surface:'board',angle:0});selected={kind:'component',id};});
$('#apply-belt').onclick=()=>mutate(()=>{for(const k of ['rx','ry','width']){const n=number('#belt-'+k),input=$('#belt-'+k);if(n<Number(input.min)||n>Number(input.max))throw new Error('Belt dimension is outside the displayed limits.');layout.belt[k]=n;}});
$('#undo').onclick=()=>{if(!past.length)return;future.push(clone(layout));layout=past.pop();pendingPin=null;rebuild();persist();historyButtons();};
$('#redo').onclick=()=>{if(!future.length)return;past.push(clone(layout));layout=future.pop();pendingPin=null;rebuild();persist();historyButtons();};
$('#reset-layout').onclick=()=>{mutate(()=>{layout=clone(manifest.defaults[mode]);selected=null;pendingPin=null;});fit();message('Default layout restored. Undo brings your design back.');};
$('#export').onclick=()=>{const blob=new Blob([JSON.stringify(layout,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=mode+'-layout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Layout exported with component positions, connections and wire bends.');};
$('#import').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>2e6)throw new Error('Choose a layout JSON smaller than 2 MB.');const imported=validateLayout(JSON.parse(await file.text()),types,mode);mutate(()=>{layout=imported;selected=null;pendingPin=null;});fit();message('Layout imported. Undo restores your previous design.');}catch(e){message('Import failed: '+e.message);}event.target.value='';};
document.addEventListener('keydown',event=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;if(event.key==='Escape'){finishDrag(true);pendingPin=null;select(null);message('Selection cleared.');}if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();removeSelection();}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='z'){event.preventDefault();$(event.shiftKey?'#redo':'#undo').click();}});
function resize(){const rect=viewport.getBoundingClientRect();camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();renderer.setSize(rect.width,rect.height);}
new ResizeObserver(resize).observe(viewport);resize();rebuild();fit();$('#editor-loading').hidden=true;if(storageProblem)message(storageProblem);
function animate(){controls.update();
  for(const c of layout.components){const element=labels.get(c.id),obj=objects.get(c.id);const p=new THREE.Vector3(0,0,c.type==='sensor'?22:14).applyMatrix4(obj.matrixWorld).project(camera);element.hidden=p.z>1||p.z< -1||(!['esp32','sensor','motor','imu'].includes(c.type)&&selected?.id!==c.id);const rect=viewport.getBoundingClientRect();element.style.left=((p.x+1)/2*rect.width)+'px';element.style.top=((-p.y+1)/2*rect.height)+'px';}
  renderer.render(scene,camera);
}
renderer.setAnimationLoop(animate);
canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();$('#editor-loading').hidden=false;$('#editor-loading').textContent='Graphics interrupted. Reload to restore the saved layout.';});
window.addEventListener('pagehide',()=>renderer.setAnimationLoop(null));

window.addEventListener('pageshow',()=>renderer.setAnimationLoop(animate));
