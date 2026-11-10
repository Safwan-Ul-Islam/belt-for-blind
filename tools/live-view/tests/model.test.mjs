import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';
import { Box3, Vector3 } from '../vendor/three/three.core.min.js';

test('the actual Blender GLB loads with all live objects and metre-scale geometry', async () => {
  const bytes = await readFile(new URL('../assets/belt_for_blind.glb', import.meta.url));
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const gltf = await new GLTFLoader().parseAsync(buffer, '');
  const objects = new Map();
  gltf.scene.traverse(obj => { if (obj.userData.belt_name) objects.set(obj.userData.belt_name, obj); });
  const root = objects.get('Belt for Blind (mm)');
  assert.ok(root);
  assert.ok(Math.abs(root.scale.x - .001) < 1e-8);
  for (const name of ['Breadboard', 'Driver breadboard']) {
    const board = objects.get(name);
    assert.ok(board, `${name} must be included beneath the electronics`);
    assert.equal(board.parent, root, `${name} must follow the live IMU rotation`);
    const parts = board.children.map(obj => obj.userData.belt_name);
    for (const prefix of ['Breadboard body', 'Centre channel', 'Holes', '+ line top', '- line bottom', 'row a', 'col 30']) {
      assert.ok(parts.some(part => part?.startsWith(prefix)), `${name} is missing ${prefix}`);
    }
    const body = board.children.find(obj => obj.userData.belt_name?.startsWith('Breadboard body'));
    const boardSize = new Box3().setFromObject(body).getSize(new Vector3());
    assert.ok(Math.abs(boardSize.x - .0835) < .001, `${name} must retain its original size`);
  }
  for (const name of ['Left', 'Center', 'Right']) {
    const beam = objects.get(`Live beam ${name}`);
    assert.ok(beam);
    const beamMaterials = [];
    beam.traverse(obj => { if (obj.material) beamMaterials.push(obj.material); });
    assert.equal(beamMaterials.length, 2, 'beam body and obstacle cap must both survive export');
    const body = objects.get(`Motor ${name} body`);
    assert.ok(body.material.color.r < body.material.color.b, 'resting motor should be silver, not a saved alert red');
    for (let k = 0; k < 3; k++) assert.ok(objects.get(`Live motor ring ${name} ${k}`));
    const position = objects.get(`HC-SR04 ${name}`).getWorldPosition(new Vector3());
    assert.ok(position.length() < .2, 'hardware remains at its real-world metre scale');
  }
  assert.ok(objects.has('GY-521 print'), 'converted text must remain in the model');
  for (const [name, obj] of objects) if (name.startsWith('Live ')) obj.visible = false;
  const size = new Box3().setFromObject(root).getSize(new Vector3());
  assert.ok(size.x < 5, 'export must retain transforms rather than baking transient live scales into the prototype');
});
