import * as THREE from 'three';

// Placas con profundidad, iluminación y oclusión reales. No son billboards.
function plaqueTexture(text, badge, small = false) {
  const canvas = document.createElement('canvas');canvas.width = 1024;canvas.height = small ? 112 : 180;
  const ctx = canvas.getContext('2d'), h = canvas.height;
  ctx.fillStyle = small ? '#f5e4eb' : '#fff7fa';ctx.fillRect(0, 0, canvas.width, h);
  ctx.strokeStyle = '#d9afc1';ctx.lineWidth = 6;ctx.strokeRect(4, 4, 1016, h - 8);
  ctx.fillStyle = '#d8afc1';ctx.fillRect(20, 20, 130, h - 40);
  ctx.fillStyle = '#573d4d';ctx.font = `600 ${small ? 44 : 46}px Arial`;ctx.textAlign = 'center';ctx.textBaseline = 'middle';ctx.fillText(badge, 85, h / 2);
  let size = small ? 58 : 68;
  do {ctx.font = `600 ${size}px Arial`;if (ctx.measureText(text).width < 800) break;size -= 2;} while (size > 30);
  ctx.fillText(text, 585, h / 2);
  for (const x of [12, 1012]) {ctx.fillStyle = '#bca8b0';ctx.beginPath();ctx.arc(x, h / 2, 3, 0, Math.PI * 2);ctx.fill();}
  const texture = new THREE.CanvasTexture(canvas);texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function mountRackSigns(view, rack, rackId) {
  const [x0, y0, x1, y1] = rack.bounds;
  const center = view.world((x0 + x1) / 2, (y0 + y1) / 2);
  const width = x1 - x0 + .8, depth = y1 - y0 + .8;
  const products = view.catalog.filter(p => p.rack === rackId);
  const group = new THREE.Group();group.position.copy(center);group.name = `signage-${rackId}`;
  const edge = view.material('sign-edge', 0xd9b1c2, {roughness:.85});
  function board(text, badge, height, y, small, twoEdges = true) {
    const face = new THREE.MeshStandardMaterial({map:plaqueTexture(text, badge, small), roughness:.9});
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(width - .08, height, .04), [edge, edge, edge, edge, face, face]);
    mesh.position.set(0, y, twoEdges ? depth / 2 + .045 : 0);mesh.castShadow = true;
    mesh.userData = {rackId, text, badge, physical: true};group.add(mesh);
    if (twoEdges) {const back = mesh.clone();back.position.z = -depth / 2 - .045;group.add(back);}
    return mesh;
  }
  const category = products[0]?.category || rackId;
  const header = board(category, rackId, .31, 3.12, false, false);
  for (const z of [0]) for (const x of [-width / 2 + .06, width / 2 - .06]) {
    const bracket = new THREE.Mesh(new THREE.BoxGeometry(.035, .49, .035), edge);
    bracket.position.set(x, 2.81, z);group.add(bracket);
  }
  const levels = products.map(product => {
    const mesh = board(product.subcategory, product.level.slice(-2), .125, product.height_m - .04, true);
    mesh.userData.level = product.level;
    return mesh;
  });
  view.scene.add(group);
  const pick = new THREE.Mesh(new THREE.BoxGeometry(width + .12, 3.3, depth + .12),
    new THREE.MeshBasicMaterial({transparent:true, opacity:0, colorWrite:false, depthWrite:false}));
  pick.position.copy(center);pick.position.y = 1.65;pick.userData.rackId = rackId;view.scene.add(pick);
  return {group, header, levels, pick, rackId, category};
}
