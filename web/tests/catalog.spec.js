import { test, expect } from './visor-fixture.js';

test('PDF catalogue, GLB downloads, real stock meshes and responsive viewer', async ({page,request})=>{
  await request.post('/api/reset',{data:{makeup:true,seed:42,orders:1,policy:'heuristic',blocked:false}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();
  expect(await page.evaluate(()=>window.warehouseViewer.scene.stockVisuals.products.size)).toBe(27);
  const appearances=await page.evaluate(()=>[...window.warehouseViewer.scene.stockVisuals.products.values()].map(p=>({
    shelf:p.shelf.count,asset:p.shelf.userData.assetSku,
    shared:p.shelf.geometry===p.cargo.geometry&&p.shelf.geometry===p.avatar.geometry&&p.shelf.geometry===p.delivered.geometry
  })));
  expect(appearances.filter(p=>p.asset)).toHaveLength(27);
  expect(appearances.every(p=>p.shared)).toBe(true);
  const layoutCheck=await page.evaluate(()=>{
    const stock=window.warehouseViewer.scene.stockVisuals;const bounds=[];
    for(const [sku,{shelf}] of stock.products){
      shelf.geometry.computeBoundingBox();
      for(let i=0;i<shelf.count;i++){
        const matrix=shelf.matrix.clone();shelf.getMatrixAt(i,matrix);
        const box=shelf.geometry.boundingBox.clone().applyMatrix4(matrix);
        bounds.push({sku,level:shelf.userData.level,box});
        if(box.min.y<shelf.userData.slot.height-1e-6)return {supported:false};
      }
    }
    let overlap=false;
    for(let i=0;i<bounds.length;i++)for(let j=i+1;j<bounds.length;j++){
      if(bounds[i].level===bounds[j].level&&bounds[i].box.intersectsBox(bounds[j].box))overlap=true;
    }
    return {supported:true,overlap,units:bounds.length};
  });
  expect(layoutCheck.supported).toBe(true);expect(layoutCheck.overlap).toBe(false);
  expect(layoutCheck.units).toBeGreaterThanOrEqual(27*5);

  await page.screenshot({path: `${process.env.SHOT_DIR || 'test-results/capturas'}/naomi-warehouse.png`,fullPage:true});
  await page.locator('#open-catalog').click();await expect(page.locator('.product-card')).toHaveCount(27);
  await page.locator('#catalog-category').selectOption('Disney');await expect(page.locator('.product-card')).toHaveCount(3);
  await page.getByRole('button',{name:/Rubor Lotso/}).click();await expect(page.locator('#product-name')).toHaveText('Rubor Lotso');
  const file=await page.request.get('/assets/products/TRD-06-01.glb');expect(file.ok()).toBe(true);expect((await file.body()).subarray(0,4).toString()).toBe('glTF');
  await page.screenshot({path: `${process.env.SHOT_DIR || 'test-results/capturas'}/naomi-catalog.png`,fullPage:true});
  await page.locator('#catalog-search').fill('inexistente');await expect(page.locator('#catalog-count')).toHaveText('0 productos');
  await page.keyboard.press('Escape');await expect(page.locator('.catalog-dialog')).not.toBeVisible();
  await page.setViewportSize({width:390,height:844});await page.locator('#open-catalog').click();await page.locator('#catalog-search').fill('');await page.locator('#catalog-category').selectOption('');
  await expect(page.locator('.product-card')).toHaveCount(27);expect(await page.locator('.catalog-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
  await page.screenshot({path: `${process.env.SHOT_DIR || 'test-results/capturas'}/naomi-mobile.png`,fullPage:true});
  await page.locator('#close-catalog').click();expect(errors).toEqual([]);
});
