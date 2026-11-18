import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PRODUCTS, createProduct } from './products.js';

export function setupCatalog() {
  const dialog=document.createElement('dialog');dialog.className='catalog-dialog';
  dialog.innerHTML=`<header><div><span class="eyebrow">SELECCIÓN DE NAOMI · CATÁLOGO DEL PDF</span><h2>El universo de productos</h2></div><button class="button" id="close-catalog" aria-label="Cerrar catálogo">Cerrar ×</button></header>
  <div class="catalog-filters"><label>Buscar producto<input id="catalog-search" type="search" placeholder="Gloss, brocha, Stitch…"></label><label>Categoría<select id="catalog-category"><option value="">Todas las categorías</option></select></label><span id="catalog-count" role="status"></span></div>
  <div class="catalog-body"><div id="catalog-grid" class="catalog-grid"></div><section class="product-preview"><canvas aria-label="Modelo 3D del producto. Arrastra para girar y usa la rueda para acercar." id="product-canvas"></canvas><h3 id="product-name"></h3><p id="product-info"></p><p class="preview-help">Arrastra para girar · Rueda para zoom</p><a id="product-download" class="button" download>Descargar asset GLB ↓</a><p class="preview-help">Modelo estilizado basado en el PDF. Escala visual aproximada.</p></section></div>`;
  document.body.append(dialog);
  const $=s=>dialog.querySelector(s), category=$('#catalog-category'), grid=$('#catalog-grid');
  for(const name of new Set(PRODUCTS.map(p=>p.category)))category.add(new Option(name,name));
  let renderer, controls, scene, camera, model, resizeObserver;
  function draw(){if(renderer && dialog.open)renderer.render(scene,camera);}
  function resize(){if(!renderer)return;const canvas=$('#product-canvas');renderer.setSize(canvas.clientWidth,canvas.clientHeight,false);camera.aspect=canvas.clientWidth/canvas.clientHeight;camera.updateProjectionMatrix();draw();}
  function choose(product){
    if(!renderer){
      renderer=new THREE.WebGLRenderer({canvas:$('#product-canvas'),antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
      scene=new THREE.Scene();scene.add(new THREE.HemisphereLight('#ffffff','#ae7e95',3));const light=new THREE.DirectionalLight('#fff4eb',4);light.position.set(2,4,3);scene.add(light);
      camera=new THREE.PerspectiveCamera(34,1,.01,20);camera.position.set(1.6,1.3,2.4);
      controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.45,0);controls.minDistance=1.4;controls.maxDistance=5;controls.enablePan=false;controls.addEventListener('change',draw);controls.update();
      resizeObserver=new ResizeObserver(resize);resizeObserver.observe(renderer.domElement);
    }
    if(model)scene.remove(model);model=createProduct(product);scene.add(model);
    $('#product-name').textContent=product.name;$('#product-info').textContent=`${product.category} / ${product.subcategory} · ${product.level} · ${product.sku} · Stock inicial: ${product.initial_stock} ${product.unit === 'kit' ? 'kits' : 'unidades'}`;
    $('#product-download').href=`/assets/products/${product.sku}.glb`;
    grid.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',button.dataset.sku===product.sku?'true':'false'));
    resize();
  }
  function filter(){
    const query=$('#catalog-search').value.toLocaleLowerCase('es');
    const selected=PRODUCTS.filter(p=>(!category.value||p.category===category.value)&&`${p.name} ${p.subcategory}`.toLocaleLowerCase('es').includes(query));
    grid.replaceChildren();$('#catalog-count').textContent=`${selected.length} productos`;
    for(const product of selected){const button=document.createElement('button');button.className='product-card';button.dataset.sku=product.sku;button.setAttribute('aria-pressed','false');
      const swatch=document.createElement('img');swatch.className='product-thumbnail';swatch.src=`/assets/products/${product.sku}.png`;swatch.alt='';swatch.loading='lazy';
      const title=document.createElement('strong');title.textContent=product.name;const detail=document.createElement('small');detail.textContent=`${product.subcategory} · ${product.level}`;button.append(swatch,title,detail);button.addEventListener('click',()=>choose(product));grid.append(button);}
    $('.product-preview').hidden=!selected.length;
    if(selected.length)choose(selected[0]);else{const empty=document.createElement('p');empty.textContent='No hay productos con ese filtro.';grid.append(empty);}
  }
  dialog.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();}});
  $('#catalog-search').addEventListener('input',filter);category.addEventListener('change',filter);
  document.querySelector('#open-catalog').addEventListener('click',()=>{dialog.showModal();filter();$('#catalog-search').focus();});
  $('#close-catalog').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{resizeObserver?.disconnect();controls?.dispose();renderer?.dispose();renderer=null;model=null;document.querySelector('#open-catalog').focus();});
}
