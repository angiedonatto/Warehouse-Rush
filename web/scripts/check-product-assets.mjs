import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PRODUCTS } from '../src/products.js';
import { VISUAL_MAPPING, createStockAppearance } from '../src/product-visuals.js';
assert.equal(PRODUCTS.length, 27);
assert.equal(new Set(PRODUCTS.map(p=>p.sku)).size, 27);
const loader=new GLTFLoader();
for(const product of PRODUCTS){
 const buffer=await readFile(new URL(`../public/assets/products/${product.sku}.glb`,import.meta.url));
 const gltf=await loader.parseAsync(buffer.buffer.slice(buffer.byteOffset,buffer.byteOffset+buffer.byteLength),'');
 assert(gltf.scene.children.length>0);
 await readFile(new URL(`../public/assets/products/${product.sku}.png`,import.meta.url));
}
for(const sku of [...PRODUCTS.map(p=>p.sku), ...Object.keys(VISUAL_MAPPING)]){
 const appearance=createStockAppearance(sku);assert(appearance);assert(PRODUCTS.some(p=>p.sku===appearance.assetSku));
 appearance.geometry.computeBoundingBox();const b=appearance.geometry.boundingBox;
 assert(Math.abs(b.min.y+.13)<1e-6,`${sku}: apoyo`);
 assert(b.max.x-b.min.x<=.190001&&b.max.y-b.min.y<=.260001&&b.max.z-b.min.z<=.190001,`${sku}: envolvente`);
 assert.equal(appearance.geometry.groups.length,appearance.materials.length);
 appearance.geometry.dispose();
}
assert.equal(createStockAppearance('TMP-E02-L3'),null);
console.log('27 GLB y miniaturas válidos; 27 productos operativos y 12 asociaciones anteriores con pivotes y envolventes conservados; fallback válido.');
