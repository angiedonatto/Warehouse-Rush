import { mkdir, writeFile } from 'node:fs/promises';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { PRODUCTS, createProduct } from '../src/products.js';
// GLTFExporter uses FileReader; Node exposes Blob but needs this small adapter.
globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(result => { this.result=result;this.onloadend?.(); }); }
};
const directory=new URL('../public/assets/products/',import.meta.url);await mkdir(directory,{recursive:true});
const exporter=new GLTFExporter();
for(const product of PRODUCTS){
 const result=await exporter.parseAsync(createProduct(product),{binary:true});
 await writeFile(new URL(`${product.sku}.glb`,directory),Buffer.from(result));
}
await writeFile(new URL('manifest.json',directory),JSON.stringify(PRODUCTS.map(p=>({sku:p.sku,name:p.name,model:p.model,file:`${p.sku}.glb`,source_page:p.source_page})),null,2)+'\n');
console.log(`Exportados ${PRODUCTS.length} assets GLB.`);
