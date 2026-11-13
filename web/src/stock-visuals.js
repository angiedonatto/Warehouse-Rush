import * as THREE from 'three';
import { LiftVisuals } from './lift-visuals.js';
import { createStockAppearance } from './product-visuals.js';
import { PackingStation } from './packing-station.js';

// Modelos de Naomi sobre SKU estables; fallback provisional sin equivalente visual.
// Una instancia representa una unidad física; reserva no elimina unidades.
const COLORS = [0xeaa4bf, 0xb9b0e5, 0xe7cbb1, 0xaed9cc, 0xf1cb85, 0xaacbe9];
const transform = new THREE.Object3D();
export class StockVisuals {
  constructor(view) {
    this.view = view;
    this.geometry = new THREE.CylinderGeometry(.095, .105, .26, 10);
    this.shelves = new THREE.Group();view.scene.add(this.shelves);
    this.cargo = new THREE.Group();view.robot.add(this.cargo);
    this.avatarCargo = new THREE.Group();view.avatar.add(this.avatarCargo);
    this.packing = new PackingStation(view);
    this.dispatched = this.packing.productRoot;
    this.products = new Map();
    this.appearances = new Map();
    this.lift = new LiftVisuals(view);
  }

  mesh(sku, quantity, parent, material) {
    if (!this.appearances.has(sku)) this.appearances.set(sku, createStockAppearance(sku));
    const appearance = this.appearances.get(sku);
    const mesh = new THREE.InstancedMesh(appearance?.geometry || this.geometry, appearance?.materials || material, Math.max(quantity, 1));
    mesh.userData.assetSku = appearance?.assetSku || null;
    mesh.userData.sku = sku;mesh.castShadow = true;parent.add(mesh);
    // Las unidades pueden desaparecer al agotarse: conservar límites de culling.
    mesh.frustumCulled = false;
    return mesh;
  }

  place(mesh, quantity, position, width = .95) {
    mesh.count = quantity;
    const columns = Math.max(1, Math.ceil(Math.sqrt(quantity)));
    const rows = Math.ceil(quantity / columns);
    for (let i = 0; i < quantity; i++) {
      transform.position.set(position.x + ((i % columns) - (columns - 1) / 2) * width / columns,
        position.y, position.z + (Math.floor(i / columns) - (rows - 1) / 2) * width / columns);
      transform.rotation.set(0, 0, 0);transform.scale.set(1, 1, 1);transform.updateMatrix();
      mesh.setMatrixAt(i, transform.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }

  animate(dt) {
    this.lift.animate(dt);
    this.packing.animate(dt);
    this.updateDeliveredPoses();
    this.cargo.position.y=this.avatarCargo.position.y=this.lift.height-.55;
  }

  updateDeliveredPoses() {
    for (const [sku, meshes] of this.products) {
      for (let i=0;i<meshes.delivered.count;i++) {
        transform.position.copy(this.packing.positionFor(sku,i));transform.rotation.set(0,0,0);transform.scale.set(1,1,1);transform.updateMatrix();
        meshes.delivered.setMatrixAt(i,transform.matrix);
      }
      meshes.delivered.instanceMatrix.needsUpdate=true;
    }
  }

  update(state, enabled, instant = false) {
    for (const group of [this.shelves, this.cargo, this.avatarCargo, this.dispatched]) group.visible = enabled;
    this.lift.update(state, enabled);
    this.packing.update(state, enabled, instant);
    if (!enabled) return;
    const lines = state.order.lines;
    const carried = state.cargo_lines || [];
    let cargoOffset = 0;
    for (const product of state.inventory.products) {
      const index = Number(product.rack.slice(1)) - 1;
      const rack = this.view.layout.racks[index];
      const [x0, y0, x1, y1] = rack.bounds;
      const layer = Number(product.level.slice(-1)) - 1;
      let meshes = this.products.get(product.sku);
      if (!meshes) {
        const material = this.view.material(`sku-${product.sku}`, COLORS[index], { roughness: .5 });
        const capacity = Math.max(5, product.stock_total + (lines.find(l => l.sku === product.sku)?.picked || 0));
        meshes = {
          shelf: this.mesh(product.sku, capacity, this.shelves, material),
          cargo: this.mesh(product.sku, capacity, this.cargo, material),
          avatar: this.mesh(product.sku, capacity, this.avatarCargo, material),
          delivered: this.mesh(product.sku, capacity, this.dispatched, material),
        };
        this.products.set(product.sku, meshes);
      }
      meshes.shelf.userData.level = product.level;
      this.place(meshes.shelf, product.stock_total, this.view.world((x0 + x1) / 2, (y0 + y1) / 2, (product.height_m ?? (.99 + layer * .8)) + .13));
      const quantity = carried.find(l => l.sku === product.sku)?.quantity || 0;
      // Distintos SKUs ocupan posiciones diferentes en la plataforma del robot.
      for (const mesh of [meshes.cargo, meshes.avatar]) {
        mesh.count = quantity;
        for (let i = 0; i < quantity; i++) {
          const slot = cargoOffset + i;
          transform.position.set((slot % 3 - 1) * .17, .70, (Math.floor(slot / 3) - .5) * .19);
          transform.rotation.set(0, 0, 0);transform.scale.set(.72, 1, .72);transform.updateMatrix();mesh.setMatrixAt(i, transform.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
      }
      cargoOffset += quantity;
      const delivered = lines.find(l => l.sku === product.sku)?.delivered || 0;
      meshes.delivered.count = delivered;
    }
    this.updateDeliveredPoses();
  }
}
