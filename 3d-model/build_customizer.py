"""Build editable Blender assemblies and a locally served component library.
Blender -b --factory-startup -P 3d-model/build_customizer.py
Optional: -- path/to/exported-layout.json (rebuild that customized assembly).
Geometry and layout coordinates are millimetres, Z up.
"""
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_model as b
OUT = HERE.parent / 'tools/live-view/assets'
OUT.mkdir(exist_ok=True)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
M = b.make_materials()
M['vero'] = b.mat('Phenolic board', '#b28a46', roughness=.72)
M['copper'] = b.mat('Copper strips', '#b76b3c', metallic=.75, roughness=.4)
M['belt'] = b.mat('Woven charcoal webbing', '#344840', roughness=.95, bump=.25, bump_scale=5)
M['stitch'] = b.mat('Sage stitching', '#a0b1a2', roughness=.9)
kit, types = {}, {}

def register(kind, group, label, pins):
    group.location = (0, 0, 0)
    group['component_type'] = kind
    kit[kind] = group
    types[kind] = {'label': label, 'pins': pins}
    return group

def cyl(name, radius, length, center, material, parent, axis=(0,0,1)):
    bm = bmesh.new()
    b.bm_cyl(bm, radius, length, center, axis=axis, segments=24)
    return b.obj_from_bm(name, bm, material, parent, bevel=.1)

b.build_esp32(M, None)
esp = bpy.data.objects['ESP32']
pins = {}
for y, names in ((12.7,b.ESP_VIN_SIDE),(-12.7,b.ESP_3V3_SIDE)):
    for i, pin in enumerate(names):
        key = 'GND2' if pin == 'GND' and y < 0 else pin
        pins[key] = [(7-i)*2.54,y,2.6]
register('esp32',esp,'ESP32 DevKit',pins)
# Flat modules face outward when mounted on the belt.
b.build_hcsr04(M,None,'Template',(0,0),0)
sensor = bpy.data.objects['HC-SR04 Template']
for obj in list(bpy.data.objects):
    if any(c.name in {'Live','Sound beams'} for c in obj.users_collection) or 'jumper housings' in obj.name:
        bpy.data.objects.remove(obj,do_unlink=True)
wrapper = b.group('Ultrasonic module',None)
sensor.parent = wrapper
sensor.location = (0,0,3)
sensor.rotation_euler = (math.pi/2,0,0)
spins = {'VCC':[3.81,11.25,3], 'Trig':[1.27,11.25,3], 'Echo':[-1.27,11.25,3], 'GND':[-3.81,11.25,3]}
for name,p in spins.items():
    cyl('Sensor pin '+name,.4,3,p,M['gold'],wrapper)
register('sensor',wrapper,'HC-SR04',spins)
b.build_motor(M,None,'Template',(0,0))
for obj in list(bpy.data.objects):
    if obj.name.startswith('Live '): bpy.data.objects.remove(obj,do_unlink=True)
register('motor',bpy.data.objects['Motor Template'],'3V coin motor',{'+':[4.6,1,1.2],'-':[4.6,-1,1.2]})
b.build_mosfet(M,None,'IRLZ44N',1)
register('mosfet',bpy.data.objects['IRLZ44N'],'IRLZ44N driver',{'G':[-2.54,0,1],'D':[0,0,1],'S':[2.54,0,1]})
imu=b.group('MPU6050 flat module',None)
b.box('IMU PCB',(21,16,1.6),(0,0,.8),M['gy521'],imu,bevel=.3)
b.box('MPU6050 chip',(4,4,1),(0,0,2.1),M['chip'],imu)
b.text('IMU legend','GY-521',2,(0,4,1.65),M['silk'],imu)
ipins={}
for i,name in enumerate(['VCC','GND','SCL','SDA','XDA','XCL','AD0','INT']):
    p=[(i-3.5)*2.54,-6,3]
    ipins[name]=p
    cyl('IMU pin '+name,.4,3,p,M['gold'],imu)
register('imu',imu,'MPU6050 / GY-521',ipins)
for kind, label, bands in [('r1k','1kΩ', ['band_brown','band_black','band_red','band_gold']),('r2k','2kΩ',['band_red','band_black','band_red','band_gold']),('r220','220Ω',['band_red','band_red','band_brown','band_gold']),('r10k','10kΩ',['band_brown','band_black','band_orange','band_gold']),('diode','1N4007',[])]:
    g=b.group(label,None)
    cyl(label+' body',1.3,6.3,(0,0,2),M['diode' if kind=='diode' else 'resistor'],g,(1,0,0))
    for x in [-6.35,6.35]:
        b.wire(label+' lead',[(x,0,0),(x,0,2),(math.copysign(3,x),0,2)],M['lead'],g,.3,smooth=False)
    for off,band in zip([-2.2,-1.2,-.2,2.2],bands):
        cyl(label+' band',1.34,.55,(off,0,2),M[band],g,(1,0,0))
    if kind=='diode': cyl('Cathode stripe',1.35,.8,(2.2,0,2),M['solder'],g,(1,0,0))
    register(kind,g,label,{'A':[-6.35,0,2],'K' if kind=='diode' else 'B':[6.35,0,2]})

vero=b.group('Vero board • 180 × 120 mm',None)
# Build a tiled ring mesh: real open holes with far fewer vertices than a
# bevelled boolean over thousands of cutters. Adjacent cells share boundaries.
def perforated_sheet(name, half_height, top, bottom, material, outer_sides):
    vertices=[]; faces=[]
    outer=[(-1.27,-half_height),(0,-half_height),(1.27,-half_height),(1.27,0),(1.27,half_height),(0,half_height),(-1.27,half_height),(-1.27,0)]
    for row in range(-22,23):
        for col in range(-34,35):
            base=len(vertices)
            for z in [top,bottom]:
                vertices.extend((col*2.54+x,row*2.54+y,z) for x,y in outer)
                vertices.extend((col*2.54+.48*math.cos(math.radians(-135+i*45)),row*2.54+.48*math.sin(math.radians(-135+i*45)),z) for i in range(8))
            for i in range(8):
                j=(i+1)%8
                for quad in [(i,j,8+j,8+i),(16+i,24+i,24+j,16+j),(8+i,8+j,24+j,24+i)]: faces.append(tuple(base+k for k in quad))
                if outer_sides and ((col==-34 and i in [6,7]) or (col==34 and i in [2,3]) or (row==-22 and i in [0,1]) or (row==22 and i in [4,5])):
                    faces.append(tuple(base+k for k in (i,16+i,16+j,j)))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    b.add_obj(name,mesh,material,vero,'Electronics')
perforated_sheet('Phenolic substrate',1.27,0,-1.6,M['vero'],True)
for x in [-88.815,88.815]: b.box('Board side border',(2.37,120,1.6),(x,0,-.8),M['vero'],vero)
for y in [-58.575,58.575]: b.box('Board end border',(175.26,2.85,1.6),(0,y,-.8),M['vero'],vero)
perforated_sheet('Continuous copper strips',.8,-1.61,-1.65,M['copper'],False)
b.text('Vero legend','VERO / 2.54 mm',2.5,(0,-58,.05),M['silk'],vero)
register('vero',vero,'Vero board',{})

belt=b.group('Adjustable belt',None)
# Elliptical webbing ring; browser scales the same authored mesh with belt size.
verts=[]; faces=[]; steps=160
for i in range(steps):
    a=2*math.pi*i/steps
    for radius,z in [(0,-25),(0,25),(-3,-25),(-3,25)]: verts.append(((170+radius)*math.sin(a),(135+radius)*math.cos(a),z))
for i in range(steps):
    j=(i+1)%steps
    for a,c in [(0,1),(1,3),(3,2),(2,0)]: faces.append((4*i+a,4*j+a,4*j+c,4*i+c))
mesh=bpy.data.meshes.new('Woven belt mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
b.add_obj('Webbing',mesh,M['belt'],belt,'Electronics')
for z in [-22,22]:
    points=[(170.3*math.sin(i*2*math.pi/steps),135.3*math.cos(i*2*math.pi/steps),z) for i in range(steps+1)]
    b.wire('Edge stitching',points,M['stitch'],belt,.35,smooth=False)
for x in [-24,24]: b.box('Buckle sides',(5,7,58),(x,139,0),M['shield'],belt,bevel=1)
for z in [-27,27]: b.box('Buckle rails',(50,7,5),(0,139,z),M['shield'],belt,bevel=1)
register('belt',belt,'Woven belt',{})

components=[]
def comp(id,kind,label,x,y): components.append({'id':id,'type':kind,'label':label,'x':x,'y':y,'z':4,'rotation':0,'surface':'board','angle':0})
comp('esp','esp32','ESP32 DevKit',-35,12)
comp('imu','imu','MPU6050',36,12)
for i,side in enumerate(['left','center','right']):
    x=(i-1)*55
    comp('sensor-'+side,'sensor',side.title()+' sensor',x,40)
    comp('motor-'+side,'motor',side.title()+' motor',x,-48)
    comp('q-'+side,'mosfet',side.title()+' MOSFET',x,-20)
    for kind,dx,dy in [('r1k',-12,0),('r2k',12,0),('r220',-13,-31),('r10k',13,-31),('diode',18,-46)]:
        comp(kind+'-'+side,kind,side.title()+' '+types[kind]['label'],x+dx,dy)
wires=[]
def wire(a,ap,bp,bpin,color):
    wires.append({'id':'w'+str(len(wires)+1),'from':{'component':a,'pin':ap},'to':{'component':bp,'pin':bpin},'color':color,'slack':7,'via':None})
red='#d45446'; black='#394a55'; blue='#438bd1'; yellow='#d1a52c'; green='#4a9d78'
for side,trig,echo,drive in [('left','D25','D34','D13'),('center','D26','D35','D33'),('right','D27','D32','D4')]:
    s='sensor-'+side; r='r1k-'+side; lo='r2k-'+side; q='q-'+side; gate='r220-'+side; pull='r10k-'+side; m='motor-'+side; d='diode-'+side
    for a,ap,z,zp,c in [('esp','VIN',s,'VCC',red),('esp','GND',s,'GND',black),('esp',trig,s,'Trig',yellow),(s,'Echo',r,'A',blue),(r,'B','esp',echo,blue),(r,'B',lo,'A',blue),(lo,'B','esp','GND',black),('esp',drive,gate,'A',green),(gate,'B',q,'G',green),(q,'G',pull,'A',green),(pull,'B','esp','GND',black),(q,'S','esp','GND',black),(q,'D',m,'-',blue),('esp','3V3',m,'+',red),(m,'+',d,'K',red),(m,'-',d,'A',blue)]: wire(a,ap,z,zp,c)
for ap,p,c in [('3V3','VCC',red),('GND','GND',black),('D21','SDA',green),('D22','SCL',yellow)]: wire('esp',ap,'imu',p,c)
def layout(mode):
    cs=json.loads(json.dumps(components))
    if mode=='belt':
        for c in cs:
            if c['type'] in ['sensor','motor']:
                side=c['id'].split('-')[-1]
                c.update(surface='belt',angle={'left':-65,'center':0,'right':65}[side]+(15 if c['type']=='motor' else 0),y=-14 if c['type']=='motor' else 5,z=5)
    return {'version':1,'mode':mode,'belt':{'rx':170,'ry':135,'width':50},'components':cs,'wires':json.loads(json.dumps(wires))}
manifest={'types':types,'defaults':{'vero':layout('vero'),'belt':layout('belt')}}
(OUT/'customizer.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Curves/fonts become meshes for portable glTF; authored part groups stay intact.
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.data.objects:
    if obj.type in {'CURVE','FONT'}: obj.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in bpy.context.selected_objects)
bpy.ops.object.convert(target='MESH')
bpy.ops.export_scene.gltf(filepath=str(OUT/'customizer.glb'),export_format='GLB',export_yup=False,export_extras=True,export_apply=True,export_animations=False)

# The .blend files contain assembled hardware, editable objects and wire curves.
def pose(c,mode,settings):
    local=Matrix.Translation((c['x'],c['y'],c['z'])) @ Matrix.Rotation(math.radians(c['rotation']),4,'Z')
    if mode=='belt' and c['surface']=='belt':
        a=math.radians(c['angle']); n=Vector((math.sin(a)/settings['rx'],math.cos(a)/settings['ry'],0)).normalized()
        tangent=Vector((-n.y,n.x,0)); up=Vector((0,0,1))
        basis=Matrix((tangent,up,n)).transposed().to_4x4()
        return Matrix.Translation(((settings['rx']+c['z'])*math.sin(a),(settings['ry']+c['z'])*math.cos(a),c['y'])) @ basis @ Matrix.Rotation(math.radians(c['rotation']),4,'Z')
    if mode=='belt' and c['surface']=='board':
        return Matrix.Translation((0,-settings['ry']-8,0)) @ Matrix.Rotation(math.pi/2,4,'X') @ local
    return local

def assemble(data,outfile):
    scene=bpy.data.scenes.new(data['mode']+' assembly')
    bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=.001
    def duplicate(src,parent=None):
        o=src.copy(); scene.collection.objects.link(o); o.parent=parent
        for child in src.children: duplicate(child,o)
        return o
    board=duplicate(kit['vero'])
    if data['mode']=='belt':
        board.matrix_world=Matrix.Translation((0,-data['belt']['ry']-8,0)) @ Matrix.Rotation(math.pi/2,4,'X')
        strap=duplicate(kit['belt']); strap.scale=(data['belt']['rx']/170,data['belt']['ry']/135,data['belt']['width']/50)
    objects={}
    for c in data['components']:
        obj=duplicate(kit[c['type']]); obj.name=c['label']; obj.matrix_world=pose(c,data['mode'],data['belt']); objects[c['id']]=obj
    bpy.context.view_layer.update()
    for w in data['wires']:
        ends=[]
        for endpoint in [w['from'],w['to']]:
            c=next(c for c in data['components'] if c['id']==endpoint['component'])
            ends.append(objects[c['id']].matrix_world @ Vector(types[c['type']]['pins'][endpoint['pin']]))
        a,z=ends; points=[a]
        if w.get('via') is not None: points.append(Vector(w['via']))
        elif data['mode']=='belt' and any(next(c for c in data['components'] if c['id']==e['component'])['surface']=='belt' for e in [w['from'],w['to']]):
            aa=math.atan2(a.x/data['belt']['rx'],a.y/data['belt']['ry']); za=math.atan2(z.x/data['belt']['rx'],z.y/data['belt']['ry']); delta=(za-aa+math.pi)%(2*math.pi)-math.pi
            for i in range(17):
                t=i/16; angle=aa+delta*t
                points.append(Vector(((data['belt']['rx']+28+w['slack'])*math.sin(angle),(data['belt']['ry']+28+w['slack'])*math.cos(angle),a.z*(1-t)+z.z*t)))
        else: points.append((a+z)/2+Vector((0,-w['slack']-5,0) if data['mode']=='belt' else (0,0,w['slack']+5)))
        points.append(z)
        b.wire(w['id'],points,b.mat(w['id']+' insulation',w['color'],roughness=.45),None,.45,coll=data['mode']+' wires')
    scene.world=bpy.data.worlds.new('Studio'); scene.world.color=(.3,.3,.3)
    # Set a useful material-preview view when opening the file.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_distance=600 if data['mode']=='belt' else 300
                area.spaces.active.shading.type='MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(outfile))

args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if args:
    data=json.loads(Path(args[0]).read_text())
    assemble(data,Path(args[1]).resolve() if len(args)>1 else HERE/'customized_layout.blend')
else:
    assemble(manifest['defaults']['vero'],HERE/'vero_layout.blend')
    assemble(manifest['defaults']['belt'],HERE/'belt_layout.blend')
print('Customizer library and Blender assemblies built.')
