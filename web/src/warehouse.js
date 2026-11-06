import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const C = { cyan: 0xf3a8c6, green: 0x42e567, yellow: 0xffbd22, red: 0xff3a42 };
const up = new THREE.Vector3(0, 1, 0);
const dummy = new THREE.Object3D();
const clamp = THREE.MathUtils.clamp;

export class WarehouseScene {
  constructor(layout, canvas, stage) {
    this.layout = layout;
    // Objetivos de estante; no se cambian geometrías ni huellas físicas.
    layout.racks.forEach((rack, i) => { layout.stations[`E${String(i + 1).padStart(2, '0')}`] = rack.bounds.slice(0, 2); });
    this.stage = stage;
    this.view = 'iso';
    this.payload = null;
    this.showRoute = true;
    this.showSensors = false;
    this.frame = 0;
    this.lastPreview = 0;
    this.elapsed = 0;
    this.lastDraw = -1;
    this.dirty = this.shadowDirty = true;
    this.materials = new Map();
    this.batches = new Map();
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.18;
    this.renderer.autoClear = false;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf8e7ef);
    this.scene.fog = new THREE.FogExp2(0xf8e7ef, 0.015);
    this.scene.add(new THREE.HemisphereLight(0xaecfe7, 0x655647, 2.1));
    this.sun = new THREE.DirectionalLight(0xffe1b4, 3.8);
    this.sun.position.set(-8, 17, 7);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    Object.assign(this.sun.shadow.camera, { left: -13, right: 13, top: 12, bottom: -12, near: 1, far: 45 });
    this.sun.shadow.bias = -0.0003;
    this.sun.shadow.normalBias = 0.035;
    this.sun.shadow.radius = 3;
    this.scene.add(this.sun);
    const fill = new THREE.DirectionalLight(0x79b7ec, 1.5);
    fill.position.set(10, 10, -8);
    this.scene.add(fill);
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.08, 110);
    this.cameras = Object.fromEntries(['iso', 'fpv', 'side', 'station'].map(name => [name, new THREE.PerspectiveCamera(44, 1, 0.06, 110)]));
    this.controls = new OrbitControls(this.camera, stage);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.09;
    this.controls.minDistance = 7;
    this.controls.maxDistance = 36;
    this.controls.maxPolarAngle = Math.PI / 2.12;
    this.controls.minPolarAngle = 0.12;
    this.controls.target.set(0, 0, 0);
    this.controls.addEventListener('change', () => { this.dirty = true; });
    this.resetCamera();
    this.buildWarehouse();
    this.flushBatches();
    this.buildRobot();
    this.buildRoutes();
    this.buildLabels();
    this.resize = () => {
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      if (this.view === 'iso') this.resetCamera();
      this.lastPreview = 0;
      this.dirty = true;
    };
    this.scroll = () => { this.dirty = true; };
    window.addEventListener('resize', this.resize);
    window.addEventListener('scroll', this.scroll, { passive: true });
    this.resize();
    this.clock = new THREE.Clock();
    this.minimap = document.querySelector('#minimap');
    this.minimapContext = this.minimap.getContext('2d');
    this.animate = this.animate.bind(this);
    this.frame = requestAnimationFrame(this.animate);
  }

  world(x, y, height = 0) {
    return new THREE.Vector3(x - (this.layout.width - 1) / 2, height, y - (this.layout.height - 1) / 2);
  }

  material(key, color, options = {}) {
    if (!this.materials.has(key)) this.materials.set(key, new THREE.MeshStandardMaterial({ color, roughness: 0.7, ...options }));
    return this.materials.get(key);
  }

  box(size, position, material, rotation = null) {
    if (!this.batches.has(material)) this.batches.set(material, []);
    this.batches.get(material).push({ size, position, rotation });
  }

  flushBatches() {
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    for (const [material, instances] of this.batches) {
      const mesh = new THREE.InstancedMesh(geometry, material, instances.length);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      instances.forEach((item, index) => {
        dummy.position.copy(item.position);
        dummy.scale.set(...item.size);
        dummy.quaternion.identity();
        if (item.rotation) dummy.quaternion.copy(item.rotation);
        dummy.updateMatrix();
        mesh.setMatrixAt(index, dummy.matrix);
      });
      mesh.computeBoundingSphere();
      this.scene.add(mesh);
    }
    this.batches.clear();
  }

  floorTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 512;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#6a6d6b';
    ctx.fillRect(0, 0, 512, 512);
    let seed = 173;
    const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < 30000; i++) {
      const value = Math.floor(70 + rand() * 100);
      ctx.fillStyle = `rgba(${value},${value},${value},.13)`;
      ctx.fillRect(rand() * 512, rand() * 512, rand() * 2 + .5, rand() * 2 + .5);
    }
    ctx.strokeStyle = '#3f484966';
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, 510, 510);
    ctx.strokeStyle = '#989c9328';
    ctx.lineWidth = 1;
    ctx.beginPath();ctx.moveTo(4, 4);ctx.lineTo(508, 4);ctx.stroke();
    for (let i = 0; i < 12; i++) {
      ctx.strokeStyle = '#343b3c15';
      const x = rand() * 500, y = rand() * 500;
      ctx.beginPath();ctx.moveTo(x, y);ctx.lineTo(x + rand() * 70, y + rand() * 9);ctx.stroke();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(this.layout.width / 2, this.layout.height / 2);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    return texture;
  }

  outline(center, width, depth, color, thickness = .035, height = .025) {
    const mat = this.material(`mark-${color}`, color, { roughness: .85 });
    for (const z of [-depth / 2, depth / 2]) this.box([width, .018, thickness], new THREE.Vector3(center.x, height, center.z + z), mat);
    for (const x of [-width / 2, width / 2]) this.box([thickness, .018, depth], new THREE.Vector3(center.x + x, height, center.z), mat);
  }

  buildWarehouse() {
    const W = this.layout.width, H = this.layout.height;
    const floor = new THREE.Mesh(new THREE.BoxGeometry(W + .2, .2, H + .2), this.material('concrete', 0x999d9b, { map: this.floorTexture(), roughness: .94 }));
    floor.position.y = -.12;
    floor.receiveShadow = true;
    this.scene.add(floor);
    const pedestal = new THREE.Mesh(new THREE.BoxGeometry(W + .5, .28, H + .5), this.material('base-edge', 0x1a2731, { metalness: .3 }));
    pedestal.position.y = -.36;
    this.scene.add(pedestal);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(150, 150), this.material('outside', 0x10212f, { roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -.52;
    ground.receiveShadow = true;
    this.scene.add(ground);
    const wall = this.material('wall', 0x68717a, { metalness: .25 });
    const wallEdge = this.material('wall-edge', 0x3c4952, { metalness: .6 });
    const wallLine = this.material('wall-line', 0x303e48, { metalness: .55 });
    const yellow = this.material('safety-yellow', 0xb88a28, { roughness: .8 });
    for (let x = 0; x < W; x++) {
      for (const y of [0, H - 1]) {
        const back = y === 0, height = back ? 2.25 : .44;
        this.wallPanel(this.world(x, y), [1, height, .28], height, wall, wallEdge, wallLine, back);
      }
    }
    for (let y = 1; y < H - 1; y++) {
      for (const x of [0, W - 1]) {
        const back = x === W - 1, height = back ? 2.25 : .44;
        this.wallPanel(this.world(x, y), [.28, height, 1], height, wall, wallEdge, wallLine, back);
      }
    }
    // La pared interior baja permite observar la geometría de colisión real.
    for (const [x, y] of this.layout.internal_walls) {
      const p = this.world(x, y);
      this.box([.98, .55, .24], p.clone().setY(.275), wall);
      this.box([.99, .055, .27], p.clone().setY(.57), yellow);
      this.box([.05, .56, .28], p.clone().add(new THREE.Vector3(-.48, .28, 0)), wallEdge);
    }
    for (const rack of this.layout.racks) this.buildRack(rack);
    for (const [name, coordinate] of Object.entries(this.layout.stations).filter(([name]) => !name.startsWith('E'))) this.buildStation(name, coordinate);
    this.buildStation('BASE', this.layout.base);
    // Delimitación de pasillos: pintura, sin añadir obstáculos al simulador.
    for (const x of [-6.9, 6.9]) this.box([.04, .012, 9], new THREE.Vector3(x, .02, -.2), yellow);
    this.box([12.6, .012, .035], new THREE.Vector3(0, .02, 4.45), yellow);
    for (let x = -6; x <= 6; x += 2) this.box([.45, .012, .035], new THREE.Vector3(x, .02, 3.5), yellow);
    this.buildBarrier();
    const lampMat = this.material('lamps', 0xffedb4, { emissive: 0xffcc77, emissiveIntensity: 2.2 });
    for (const x of [-6, -2, 2, 6]) {
      this.box([.32, .12, .14], new THREE.Vector3(x, 1.8, -5.82), lampMat);
      const lamp = new THREE.PointLight(0xffd08a, 2.4, 4, 2);
      lamp.position.set(x, 1.7, -5.5);
      this.scene.add(lamp);
    }
    // Señales y pequeños armarios fijados a pared; no ocupan celdas transitables.
    const cabinet = this.material('cabinet', 0x48545b, { metalness: .6 });
    const red = this.material('extinguisher', 0xb9312c, { roughness: .5 });
    for (const x of [-5, 1, 5]) {
      this.box([.32, .55, .15], new THREE.Vector3(x, .95, -5.78), cabinet);
      this.box([.06, .08, .025], new THREE.Vector3(x + .09, 1, -5.69), yellow);
      this.box([.14, .33, .12], new THREE.Vector3(x - .5, .75, -5.75), red);
    }
  }

  wallPanel(p, size, height, wall, edge, line, detailed) {
    this.box(size, p.clone().setY(height / 2), wall);
    this.box([size[0] + .025, .065, size[2] + .025], p.clone().setY(height), edge);
    const isX = size[0] > size[2];
    this.box(isX ? [.055, height, .32] : [.32, height, .055], p.clone().add(new THREE.Vector3(isX ? -.47 : 0, height / 2, isX ? 0 : -.47)), edge);
    if (detailed) for (const h of [.35, .58, 1.5]) this.box([size[0], .018, size[2] + .005], p.clone().setY(h), line);
  }

  buildRack(rack) {
    const [x0, y0, x1, y1] = rack.bounds;
    const center = this.world((x0 + x1) / 2, (y0 + y1) / 2);
    const width = x1 - x0 + .8, depth = y1 - y0 + .8;
    const steel = this.material('steel', 0x343e46, { metalness: .72, roughness: .43 });
    const beam = this.material('beam', 0xc87b20, { metalness: .45, roughness: .58 });
    const shelf = this.material('shelf', 0x60707a, { metalness: .55, roughness: .65 });
    const tape = this.material('tape', 0xc5a374, { roughness: .95 });
    const label = this.material('box-label', 0xc8c6ab);
    this.outline(center, width + .32, depth + .32, 0xb5953d, .045);
    for (const dx of [-width / 2, width / 2]) for (const dz of [-depth / 2, depth / 2]) {
      this.box([.065, 2.65, .065], center.clone().add(new THREE.Vector3(dx, 1.325, dz)), steel);
      this.box([.14, .065, .14], center.clone().add(new THREE.Vector3(dx, .04, dz)), steel);
      for (const h of [.14, .23, .32]) this.box([.09, .07, .09], center.clone().add(new THREE.Vector3(dx, h, dz)), this.material('post-protection', 0xe8ae29));
    }
    for (const h of [.15, .95, 1.75, 2.56]) {
      this.box([width, .065, depth], center.clone().add(new THREE.Vector3(0, h, 0)), shelf);
      for (const dz of [-depth / 2, depth / 2]) this.box([width + .06, .12, .055], center.clone().add(new THREE.Vector3(0, h, dz)), beam);
      for (const dx of [-width / 2, width / 2]) this.box([.055, .10, depth], center.clone().add(new THREE.Vector3(dx, h, 0)), steel);
    }
    for (let layer = 0; layer < 4; layer++) for (let col = 0; col < 3; col++) for (let row = 0; row < 2; row++) {
      const variation = (x0 + y0 + layer * 3 + col * 7 + row) % 4;
      const h = [.38, .48, .42, .56][variation];
      const w = [.43, .48, .46, .40][variation];
      const position = center.clone().add(new THREE.Vector3((col - 1) * .53, .21 + layer * .8 + h / 2, (row - .5) * .78));
      const carton = this.material(`carton-${variation}`, [0x9d7449, 0xb88b55, 0x92704d, 0xc19a69][variation], { roughness: .96 });
      this.box([w, h, .63], position, carton);
      this.box([.055, .007, .64], position.clone().add(new THREE.Vector3(0, h / 2 + .005, 0)), tape);
      this.box([.056, h * .65, .007], position.clone().add(new THREE.Vector3(0, h * .17, .32)), tape);
      if ((col + layer) % 2 === 0) this.box([.12, .08, .008], position.clone().add(new THREE.Vector3(.10, 0, .321)), label);
    }
    // Arriostramiento diagonal en el lateral del rack.
    for (const dx of [-width / 2, width / 2]) {
      const start = center.clone().add(new THREE.Vector3(dx, .2, -depth / 2));
      const end = center.clone().add(new THREE.Vector3(dx, 2.5, depth / 2));
      const direction = end.clone().sub(start);
      this.box([.035, direction.length(), .035], start.add(end).multiplyScalar(.5), steel,
        new THREE.Quaternion().setFromUnitVectors(up, direction.normalize()));
    }
  }

  buildStation(name, coordinate) {
    const p = this.world(...coordinate), color = name === 'BASE' ? C.green : name === 'DELIVERY' ? C.yellow : C.cyan;
    const pad = this.material(`pad-${name}`, color, { transparent: true, opacity: .17, emissive: color, emissiveIntensity: .9, depthWrite: false });
    this.box([.96, .018, .96], p.clone().setY(.02), pad);
    const neon = this.material(`neon-${name}`, color, { emissive: color, emissiveIntensity: 2.5, roughness: .4 });
    for (const dz of [-.46, .46]) this.box([.96, .025, .035], p.clone().add(new THREE.Vector3(0, .045, dz)), neon);
    for (const dx of [-.46, .46]) this.box([.035, .025, .96], p.clone().add(new THREE.Vector3(dx, .045, 0)), neon);
    if (name !== 'BASE') {
      const pallet = this.material('pallet', 0x715738);
      for (const dx of [-.26, 0, .26]) this.box([.13, .12, .64], p.clone().add(new THREE.Vector3(dx, .09, 0)), pallet);
      for (const dz of [-.23, 0, .23]) this.box([.68, .045, .14], p.clone().add(new THREE.Vector3(0, .17, dz)), pallet);
      this.box([.52, .36, .47], p.clone().setY(.38), this.material('station-carton', 0xb68e5b));
      this.box([.07, .008, .48], p.clone().setY(.564), this.material('station-tape', 0xd6b886));
      this.box([.14, .09, .008], p.clone().add(new THREE.Vector3(.09, .38, .24)), this.material('shipping-label', 0xd7d4ba));
    } else {
      const baseMark = this.material('base-mark', 0x88ff94, { emissive: 0x33e84a, emissiveIntensity: 1.2 });
      for (const dx of [-.12, .12]) this.box([.025, .012, .35], p.clone().add(new THREE.Vector3(dx, .045, 0)), baseMark);
      for (const dz of [-.17, .17]) this.box([.24, .012, .025], p.clone().add(new THREE.Vector3(0, .045, dz)), baseMark);
    }
    const glow = new THREE.PointLight(color, 1.8, 2.3, 2);
    glow.position.copy(p).y = .35;
    this.scene.add(glow);
  }

  buildBarrier() {
    this.barrier = new THREE.Group();
    const p = this.world(...this.layout.blockable_cells[0]);
    this.barrier.position.copy(p);
    const stripeCanvas = document.createElement('canvas');
    stripeCanvas.width = stripeCanvas.height = 128;
    const ctx = stripeCanvas.getContext('2d');
    ctx.fillStyle = '#e83938';ctx.fillRect(0, 0, 128, 128);
    ctx.strokeStyle = '#ffb8a1';ctx.lineWidth = 18;
    for (let x = -128; x < 256; x += 38) { ctx.beginPath();ctx.moveTo(x, 0);ctx.lineTo(x + 128, 128);ctx.stroke(); }
    const stripes = new THREE.CanvasTexture(stripeCanvas);
    stripes.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshStandardMaterial({ map: stripes, color: 0xff9999, emissive: 0x9f1717, emissiveIntensity: .6, roughness: .6 });
    const bar = new THREE.Mesh(new THREE.BoxGeometry(.96, .48, .12), material);
    bar.position.y = .48;bar.castShadow = true;this.barrier.add(bar);
    const floor = new THREE.Mesh(new THREE.BoxGeometry(.98, .016, .9), new THREE.MeshStandardMaterial({ color: C.red, transparent: true, opacity: .22, emissive: C.red, emissiveIntensity: .6, depthWrite: false }));
    floor.position.y = .025;this.barrier.add(floor);
    for (const dx of [-.48, .48]) {
      const post = new THREE.Mesh(new THREE.CylinderGeometry(.065, .08, .78, 8), this.material('bollard', 0xe2b344));
      post.position.set(dx, .39, 0);post.castShadow = true;this.barrier.add(post);
      for (const h of [.15, .35, .55]) {
        const band = new THREE.Mesh(new THREE.CylinderGeometry(.071, .077, .08, 8), this.material('bollard-black', 0x20282b));
        band.position.set(dx, h, 0);this.barrier.add(band);
      }
      const light = new THREE.Mesh(new THREE.SphereGeometry(.055, 8, 6), this.material('hazard-light', 0xff5555, { emissive: C.red, emissiveIntensity: 3 }));
      light.position.set(dx, .81, 0);this.barrier.add(light);
    }
    this.barrierGlow = new THREE.PointLight(C.red, 3, 3, 2);
    this.barrierGlow.position.set(0, .6, .2);this.barrier.add(this.barrierGlow);
    this.scene.add(this.barrier);
  }

  roundedBody(width, depth, height, radius, material) {
    const shape = new THREE.Shape();
    const x = -width / 2, z = -depth / 2;
    shape.moveTo(x + radius, z);shape.lineTo(x + width - radius, z);
    shape.quadraticCurveTo(x + width, z, x + width, z + radius);
    shape.lineTo(x + width, z + depth - radius);shape.quadraticCurveTo(x + width, z + depth, x + width - radius, z + depth);
    shape.lineTo(x + radius, z + depth);shape.quadraticCurveTo(x, z + depth, x, z + depth - radius);
    shape.lineTo(x, z + radius);shape.quadraticCurveTo(x, z, x + radius, z);
    const geo = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: true, bevelSegments: 2, steps: 1, bevelSize: .025, bevelThickness: .025, curveSegments: 5 });
    geo.rotateX(-Math.PI / 2);
    geo.translate(0, 0, 0);
    const mesh = new THREE.Mesh(geo, material);mesh.castShadow = true;mesh.receiveShadow = true;
    return mesh;
  }

  buildRobot() {
    this.robot = new THREE.Group();
    const body = this.roundedBody(.72, .76, .23, .14, this.material('robot-white', 0xdce2e4, { metalness: .28, roughness: .32 }));
    body.position.y = .24;this.robot.add(body);
    const bumper = this.roundedBody(.76, .8, .11, .14, this.material('robot-bumper', 0x17252d, { metalness: .3, roughness: .45 }));
    bumper.position.y = .15;this.robot.add(bumper);
    const top = this.roundedBody(.6, .61, .05, .08, this.material('robot-top', 0x9da9af, { metalness: .7, roughness: .35 }));
    top.position.y = .49;this.robot.add(top);
    const tire = this.material('tire', 0x11191f, { roughness: .88 });
    const hub = this.material('hub', 0x5c6d78, { metalness: .75, roughness: .3 });
    this.wheels = [];
    for (const x of [-.36, .36]) for (const z of [-.24, .24]) {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(.135, .135, .11, 18), tire);
      wheel.rotation.z = Math.PI / 2;wheel.position.set(x, .145, z);wheel.castShadow = true;this.robot.add(wheel);this.wheels.push(wheel);
      const cap = new THREE.Mesh(new THREE.CylinderGeometry(.067, .067, .115, 14), hub);
      cap.rotation.z = Math.PI / 2;cap.position.copy(wheel.position);this.robot.add(cap);
    }
    const sensor = new THREE.Mesh(new THREE.BoxGeometry(.43, .105, .05), this.material('sensor-black', 0x071822, { roughness: .2, metalness: .7 }));
    sensor.position.set(0, .33, -.41);this.robot.add(sensor);
    const led = new THREE.Mesh(new THREE.BoxGeometry(.32, .023, .056), this.material('robot-led', C.cyan, { emissive: C.cyan, emissiveIntensity: 3 }));
    led.position.set(0, .32, -.44);this.robot.add(led);
    const lidar = new THREE.Mesh(new THREE.CylinderGeometry(.07, .08, .07, 18), hub);
    lidar.position.set(0, .60, .2);this.robot.add(lidar);
    this.cargo = new THREE.Group();
    const carton = new THREE.Mesh(new THREE.BoxGeometry(.48, .35, .44), this.material('robot-carton', 0xb38a56, { roughness: .95 }));
    carton.position.y = .75;carton.castShadow = true;this.cargo.add(carton);
    const tape = new THREE.Mesh(new THREE.BoxGeometry(.065, .008, .45), this.material('robot-tape', 0xd4b68b));
    tape.position.y = .93;this.cargo.add(tape);this.robot.add(this.cargo);
    this.cargo.visible = false;
    this.scene.add(this.robot);
    this.targetPosition = this.world(...this.layout.base);
    this.robot.position.copy(this.targetPosition);
    this.targetYaw = 0;
    this.avatarScene = new THREE.Scene();
    this.avatarScene.background = new THREE.Color(0x102534);
    this.avatarScene.add(new THREE.HemisphereLight(0xd9efff, 0x2f4355, 3));
    const light = new THREE.DirectionalLight(0xffe9c6, 3);light.position.set(-2, 4, 3);this.avatarScene.add(light);
    this.avatar = this.robot.clone(true);this.avatar.position.set(0, -.05, 0);this.avatar.rotation.y = -.4;this.avatarScene.add(this.avatar);
    this.avatarCargo = this.avatar.children[this.robot.children.indexOf(this.cargo)];
    this.avatarCamera = new THREE.PerspectiveCamera(35, 1, .01, 10);
    this.avatarCamera.position.set(-1.4, 1.35, -1.8);this.avatarCamera.lookAt(0, .42, 0);
  }

  buildRoutes() {
    this.routeMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(.045, .018, .17), this.material('route-cyan', C.cyan, { emissive: C.cyan, emissiveIntensity: 1.7 }), 1800);
    this.routeMesh.count = 0;this.routeMesh.frustumCulled = false;this.scene.add(this.routeMesh);
    this.trailMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(.032, .012, .032), this.material('trail', 0x63bacb, { emissive: 0x14495a, transparent: true, opacity: .5 }), 250);
    this.trailMesh.count = 0;this.trailMesh.frustumCulled = false;this.scene.add(this.trailMesh);
    this.sensorGeometry = new THREE.BufferGeometry();
    this.sensorGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(8 * 6), 3));
    this.sensorLines = new THREE.LineSegments(this.sensorGeometry, new THREE.LineBasicMaterial({ color: 0x80ebff, transparent: true, opacity: .4, depthWrite: false }));
    this.sensorLines.frustumCulled = false;this.sensorLines.visible = false;this.scene.add(this.sensorLines);
  }

  buildLabels() {
    this.labels = [];
    const container = document.querySelector('#station-labels');
    const entries = [['BASE', this.layout.base], ...Object.entries(this.layout.stations), ['BLOCK', this.layout.blockable_cells[0]]];
    for (const [name, coordinate] of entries) {
      const el = document.createElement('div');
      el.className = `station-label ${name === 'BASE' ? 'base' : name === 'DELIVERY' ? 'delivery' : name === 'BLOCK' ? 'blocked' : ''}`;
      const title = { BASE: 'BASE / INICIO', P1: 'RECOGIDA 1', P2: 'RECOGIDA 2', DELIVERY: 'ENTREGA', BLOCK: 'PASILLO BLOQUEADO' }[name] || name;
      el.innerHTML = `${name === 'BLOCK' ? '' : '<span class="station-icon"></span>'}<span>${title}${name.startsWith('P') ? `<small>(${name})</small>` : name === 'DELIVERY' ? '<small>(D)</small>' : ''}</span>`;
      if (name.startsWith('E')) {
        el.classList.add('rack-label');el.tabIndex = 0;el.setAttribute('role', 'button');
        const index = Number(name.slice(1)) - 1;
        const categories = ['Maquillaje', 'Cuidado de la piel', 'Brochas y esponjas', 'Accesorios', 'Capilar', 'Disney'];
        el.innerHTML = `<span>${name}</span><span class="rack-category">${categories[index]} · L1 / L2 / L3</span>`;
        el.addEventListener('pointerdown', e => e.stopPropagation());
        el.addEventListener('click', () => this.onRackSelect?.(name));
        el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault();this.onRackSelect?.(name); } });
      }
      container.append(el);
      this.labels.push({ name, el, position: this.world(...coordinate, name === 'BLOCK' ? 1.15 : name === 'BASE' ? .7 : 1.25) });
    }
  }

  setState(payload, instant = false) {
    this.payload = payload;
    const s = payload.state;
    this.targetPosition = this.world(s.x, s.y);
    this.targetYaw = -s.theta * Math.PI / 2;
    if (instant) { this.robot.position.copy(this.targetPosition);this.robot.rotation.y = this.targetYaw; }
    this.cargo.visible = Boolean(s.carga);
    this.avatarCargo.visible = Boolean(s.carga);
    this.barrier.visible = s.pasillo_bloqueado;
    const route = payload.route;
    let count = 0;
    for (let i = 1; i < route.length; i++) {
      const start = this.world(...route[i - 1], .065), end = this.world(...route[i], .065);
      const dir = end.clone().sub(start);
      for (let j = 0; j < 4; j++) {
        dummy.position.copy(start).lerp(end, (j + .5) / 4);
        dummy.rotation.set(0, Math.atan2(dir.x, dir.z), 0);dummy.scale.set(1, 1, 1);dummy.updateMatrix();
        this.routeMesh.setMatrixAt(count++, dummy.matrix);
      }
    }
    this.routeMesh.count = count;this.routeMesh.instanceMatrix.needsUpdate = true;
    payload.trail.forEach((cell, index) => {
      dummy.position.copy(this.world(...cell, .045));dummy.rotation.set(0, 0, 0);dummy.scale.set(1, 1, 1);dummy.updateMatrix();this.trailMesh.setMatrixAt(index, dummy.matrix);
    });
    this.trailMesh.count = payload.trail.length;this.trailMesh.instanceMatrix.needsUpdate = true;
    this.dirty = this.shadowDirty = true;
    this.lastPreview = 0;
  }

  resetCamera() {
    const aspect = this.stage.clientWidth / this.stage.clientHeight;
    const fit = Math.max(1, 1.45 / aspect);
    this.camera.position.set(-13.8, 17.5, 17.8).multiplyScalar(fit);
    this.controls.maxDistance = Math.max(36, this.camera.position.length() * 1.3);
    this.controls.target.set(0, .15, .1);
    this.camera.lookAt(this.controls.target);
    this.controls.update();
  }

  selectCamera(name) {
    this.view = name;this.controls.enabled = name === 'iso';
    this.dirty = true;
    if (name === 'iso') this.resetCamera();
    this.lastPreview = 0;
  }

  cameraPositions() {
    const p = this.robot.position;
    const forward = new THREE.Vector3(0, 0, -1).applyAxisAngle(up, this.robot.rotation.y);
    this.cameras.iso.position.set(-12, 15, 15);this.cameras.iso.lookAt(0, .4, 0);
    this.cameras.fpv.position.copy(p).add(new THREE.Vector3(0, 1.10, 0)).addScaledVector(forward, .06);
    this.cameras.fpv.lookAt(p.clone().addScaledVector(forward, 5).add(new THREE.Vector3(0, .85, 0)));
    this.cameras.side.position.copy(p).add(new THREE.Vector3(-2.7, 1.35, 2.5));
    this.cameras.side.lookAt(p.clone().setY(.45));
    const target = this.payload?.state.objetivo;
    const station = target ? this.world(...this.layout.stations[target]) : this.world(...this.layout.stations.DELIVERY);
    const side = target === 'DELIVERY' ? -1 : 1;
    this.cameras.station.position.copy(station).add(new THREE.Vector3(-2 * side, 2.15, 2.35));
    this.cameras.station.lookAt(station.clone().setY(.3));
    if (this.view !== 'iso') {
      this.camera.position.copy(this.cameras[this.view].position);
      this.camera.quaternion.copy(this.cameras[this.view].quaternion);
    }
  }

  renderIn(element, camera, scene = this.scene) {
    const rect = element.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight || rect.width === 0) return;
    const left = Math.max(0, rect.left), bottom = window.innerHeight - rect.bottom;
    const clipBottom = Math.max(0, bottom), clipTop = Math.min(window.innerHeight, window.innerHeight - rect.top);
    camera.aspect = rect.width / rect.height;camera.updateProjectionMatrix();
    this.renderer.setViewport(rect.left, bottom, rect.width, rect.height);
    this.renderer.setScissor(left, clipBottom, Math.min(rect.right, window.innerWidth) - left, clipTop - clipBottom);
    this.renderer.setScissorTest(true);
    this.renderer.setClearColor(scene.background || 0x0b1b28, scene.background ? 1 : 0);
    this.renderer.clear(true, true, true);
    this.renderer.render(scene, camera);
  }

  updateLabels() {
    const w = this.stage.clientWidth, h = this.stage.clientHeight;
    for (const { name, el, position } of this.labels) {
      const v = position.clone().project(this.camera);
      const x = (v.x * .5 + .5) * w, y = (-v.y * .5 + .5) * h;
      const visible = v.z > -1 && v.z < 1 && x > 20 && x < w - 20 && y > 45 && y < h - 25 && (name !== 'BLOCK' || this.barrier.visible);
      el.style.display = visible ? 'flex' : 'none';el.style.left = `${x}px`;el.style.top = `${y}px`;
    }
  }

  updateSensors() {
    if (!this.payload) return;
    const positions = this.sensorGeometry.attributes.position.array;
    const directions = [[0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]];
    directions.forEach(([dx, dz], i) => {
      const distance = this.payload.observation[i] * this.layout.simulation.sensor_range;
      const length = Math.hypot(dx, dz), p = this.robot.position;
      positions.set([p.x, .32, p.z, p.x + dx / length * distance, .32, p.z + dz / length * distance], i * 6);
    });
    this.sensorGeometry.attributes.position.needsUpdate = true;
  }

  drawMinimap() {
    const canvas = this.minimap, rect = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio, 2);
    if (canvas.width !== Math.round(rect.width * dpr) || canvas.height !== Math.round(rect.height * dpr)) { canvas.width = Math.round(rect.width * dpr);canvas.height = Math.round(rect.height * dpr); }
    const ctx = this.minimapContext, W = this.layout.width, H = this.layout.height;
    const cw = canvas.width / W, ch = canvas.height / H;
    ctx.fillStyle = '#424a4c';ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (let x = 0; x < W; x++) for (let y = 0; y < H; y++) {
      ctx.fillStyle = (x + y) % 2 ? '#4a5152' : '#4f5655';ctx.fillRect(x * cw + .4, y * ch + .4, cw - .8, ch - .8);
    }
    const wall = (x, y) => { ctx.fillStyle = '#819096';ctx.fillRect(x * cw + 1, y * ch + 1, cw - 2, ch - 2);ctx.fillStyle = '#4e606b';ctx.fillRect(x * cw + 2, y * ch + ch * .65, cw - 3, ch * .23); };
    for (let x = 0; x < W; x++) { wall(x, 0);wall(x, H - 1); }
    for (let y = 1; y < H - 1; y++) { wall(0, y);wall(W - 1, y); }
    this.layout.internal_walls.forEach(([x, y]) => wall(x, y));
    for (const { bounds: [x0, y0, x1, y1] } of this.layout.racks) {
      const x = x0 * cw + 2, y = y0 * ch + 2, w = (x1 - x0 + 1) * cw - 4, h = (y1 - y0 + 1) * ch - 4;
      ctx.fillStyle = '#29343b';ctx.fillRect(x + 2, y + 3, w, h);ctx.fillStyle = '#a17a4f';ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = '#d2a553';ctx.lineWidth = 1.5;ctx.strokeRect(x, y, w, h);ctx.strokeStyle = '#58472f';
      ctx.beginPath();ctx.moveTo(x + w / 2, y);ctx.lineTo(x + w / 2, y + h);ctx.moveTo(x, y + h / 2);ctx.lineTo(x + w, y + h / 2);ctx.stroke();
    }
    if (this.payload && this.showRoute) {
      ctx.strokeStyle = '#53dbf2';ctx.lineWidth = 1.5 * dpr;ctx.setLineDash([3 * dpr, 3 * dpr]);ctx.beginPath();
      this.payload.route.forEach(([x, y], i) => { const px = (x + .5) * cw, py = (y + .5) * ch; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });ctx.stroke();ctx.setLineDash([]);
    }
    if (this.payload?.state.pasillo_bloqueado) for (const [x, y] of this.layout.blockable_cells) {
      ctx.fillStyle = '#e34847';ctx.fillRect(x * cw, y * ch, cw, ch);ctx.strokeStyle = '#ffc0ab';ctx.lineWidth = 2;
      ctx.beginPath();ctx.moveTo(x * cw, (y + 1) * ch);ctx.lineTo((x + 1) * cw, y * ch);ctx.stroke();
    }
    const marker = (cell, text, color) => {
      const [x, y] = cell, px = (x + .5) * cw, py = (y + .5) * ch, size = cw * 1.3;
      ctx.fillStyle = '#11252ce8';ctx.strokeStyle = color;ctx.lineWidth = 1.7 * dpr;
      ctx.beginPath();ctx.roundRect(px - size / 2, py - size / 2, size, size, 2 * dpr);ctx.fill();ctx.stroke();
      ctx.fillStyle = color;ctx.font = `bold ${Math.max(8, cw * .68)}px Arial`;ctx.textAlign = 'center';ctx.textBaseline = 'middle';ctx.fillText(text, px, py + .5);
    };
    marker(this.layout.base, 'B', '#71ed82');
    for (const [name, cell] of Object.entries(this.layout.stations)) marker(cell, name === 'DELIVERY' ? 'D' : name, name === 'DELIVERY' ? '#ffcc46' : '#56e4f3');
    if (this.payload) {
      const x = (this.robot.position.x + (W - 1) / 2 + .5) * cw, y = (this.robot.position.z + (H - 1) / 2 + .5) * ch;
      ctx.save();ctx.translate(x, y);ctx.rotate(-this.robot.rotation.y);ctx.fillStyle = '#fff';ctx.shadowColor = '#50dfff';ctx.shadowBlur = 5;
      ctx.beginPath();ctx.moveTo(0, -ch * .34);ctx.lineTo(cw * .28, ch * .26);ctx.lineTo(0, ch * .12);ctx.lineTo(-cw * .28, ch * .26);ctx.closePath();ctx.fill();ctx.restore();
    }
  }

  animate() {
    this.frame = requestAnimationFrame(this.animate);
    const dt = Math.min(this.clock.getDelta(), .08);
    this.elapsed += dt;
    if (this.renderer.domElement.width === 0) return;
    this.robot.position.lerp(this.targetPosition, 1 - Math.exp(-dt * (this.motionSpeed || 9)));
    const angle = Math.atan2(Math.sin(this.targetYaw - this.robot.rotation.y), Math.cos(this.targetYaw - this.robot.rotation.y));
    const moving = this.robot.position.distanceToSquared(this.targetPosition) > .00001 || Math.abs(angle) > .001;
    this.robot.rotation.y += angle * (1 - Math.exp(-dt * 12));
    if (this.payload?.state.v) this.wheels.forEach(wheel => { wheel.rotation.x += dt * 4; });
    this.barrierGlow.intensity = 2.7 + Math.sin(this.elapsed * 5) * .5;
    this.routeMesh.visible = this.trailMesh.visible = this.showRoute;
    this.sensorLines.visible = this.showSensors;
    if (this.showSensors) this.updateSensors();
    if (this.view === 'iso') this.controls.update();
    // 30 fps durante movimiento; 4 fps en reposo para la baliza. Evitar trabajo
    // continuo de GPU cuando la misión está en pausa.
    if (this.elapsed - this.lastDraw < 1 / 30) return;
    if (!this.dirty && !moving && this.elapsed - this.lastDraw < .25) return;
    this.lastDraw = this.elapsed;this.dirty = false;
    this.cameraPositions();
    this.renderer.setScissorTest(false);
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.clear(true, true, true);
    this.renderer.shadowMap.needsUpdate = this.shadowDirty || moving;
    this.shadowDirty = false;
    this.renderIn(this.stage, this.camera);
    this.renderer.shadowMap.needsUpdate = false;
    this.updateLabels();
    for (const name of ['iso', 'fpv', 'side', 'station']) this.renderIn(document.querySelector(`#preview-${name}`), this.cameras[name]);
    this.renderIn(document.querySelector('#robot-portrait'), this.avatarCamera, this.avatarScene);
    this.drawMinimap();
  }

  dispose() {
    cancelAnimationFrame(this.frame);window.removeEventListener('resize', this.resize);window.removeEventListener('scroll', this.scroll);this.controls.dispose();
    const geometries = new Set(), materials = new Set();
    for (const scene of [this.scene, this.avatarScene]) scene.traverse(obj => { if (obj.geometry) geometries.add(obj.geometry);if (obj.material) materials.add(obj.material); });
    geometries.forEach(g => g.dispose());materials.forEach(m => { m.map?.dispose();m.dispose(); });this.renderer.dispose();
  }
}
