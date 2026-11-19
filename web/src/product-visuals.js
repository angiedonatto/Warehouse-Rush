import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { PRODUCTS, createProduct } from './products.js';

// Los SKU TRD operativos usan su modelo directamente. Estas asociaciones TMP se
// conservan sólo para representar sesiones antiguas, sin renombrar su inventario.
export const VISUAL_MAPPING = Object.freeze({
  'TMP-E01-L1': 'TRD-01-09', 'TMP-E01-L2': 'TRD-01-10', 'TMP-E01-L3': 'TRD-01-04',
  'TMP-E02-L1': 'TRD-02-01', 'TMP-E02-L2': 'TRD-02-04',
  'TMP-E03-L1': 'TRD-03-01', 'TMP-E03-L2': 'TRD-03-02',
  'TMP-E04-L1': 'TRD-04-02', 'TMP-E04-L3': 'TRD-04-03',
  'TMP-E05-L1': 'TRD-05-01', 'TMP-E05-L2': 'TRD-05-02',
  'TMP-E06-L3': 'TRD-06-01',
});

// Una sola geometría instanciada por SKU, compartida en estante, robot, retrato y caja.
// Se ajusta a la envolvente anterior (0.19 × 0.26 × 0.19 m), apoyada en la misma base.
export function createStockAppearance(sku) {
  const asset = PRODUCTS.find(p => p.sku === (VISUAL_MAPPING[sku] || sku));
  if (!asset) return null;
  const model = createProduct(asset), geometries = [], materials = [];
  model.updateMatrixWorld(true);
  model.traverse(object => {
    if (!object.isMesh) return;
    const geometry = object.geometry.index ? object.geometry.toNonIndexed() : object.geometry.clone();
    geometry.applyMatrix4(object.matrixWorld);geometries.push(geometry);materials.push(object.material);
  });
  const geometry = mergeGeometries(geometries, true);
  geometries.forEach(g => g.dispose());
  if (!geometry) return null;
  geometry.computeBoundingBox();
  const size = geometry.boundingBox.getSize(new THREE.Vector3());
  const center = geometry.boundingBox.getCenter(new THREE.Vector3());
  const scale = Math.min(.19 / size.x, .26 / size.y, .19 / size.z);
  geometry.translate(-center.x, -center.y, -center.z);geometry.scale(scale, scale, scale);
  geometry.translate(0, -.13 + size.y * scale / 2, 0);geometry.computeBoundingSphere();
  return { geometry, materials, assetSku: asset.sku };
}
