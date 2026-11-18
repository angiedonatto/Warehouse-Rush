import {test, expect} from '@playwright/test';

test('wide warehouse has mounted signs, no floating rack labels and selectable racks', async ({page})=>{
  const response=await page.request.post('/api/reset',{data:{makeup:true,orders:1,seed:42,policy:'heuristic',blocked:true}});
  expect(response.ok()).toBeTruthy();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('.rack-label, .rack-level-label')).toHaveCount(0);
  const signs=await page.evaluate(()=>{
    const s=window.warehouseViewer.scene;
    return {width:s.layout.width,height:s.layout.height,racks:s.rackSigns.map(sign=>({category:sign.category,header:sign.header.type,levels:sign.levels.map(mesh=>mesh.userData.text),depth:sign.header.geometry.parameters.depth}))};
  });
  expect([signs.width,signs.height]).toEqual([25,19]);
  expect(signs.racks).toHaveLength(6);
  expect(signs.racks[0]).toEqual({category:'Maquillaje',header:'Mesh',levels:['Rostro','Labios','Cejas / Ojos'],depth:.04});
  expect(signs.racks.reduce((n,r)=>n+r.levels.length,0)).toBe(18);
  const point=await page.evaluate(()=>{
    const s=window.warehouseViewer.scene,rect=s.stage.getBoundingClientRect();
    const p=s.rackSigns[3].header.getWorldPosition(s.robot.position.clone()).project(s.camera);
    return {x:rect.left+(p.x+1)*rect.width/2,y:rect.top+(1-p.y)*rect.height/2};
  });
  await page.mouse.click(point.x,point.y);
  await expect(page.locator('#rack-detail')).toContainText('E04 · Accesorios');
  await expect(page.locator('#rack-detail')).toContainText('Disponible');
  await page.screenshot({path: `${process.env.SHOT_DIR || 'test-results/capturas'}/06-bodega-amplia.png`});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path: `${process.env.SHOT_DIR || 'test-results/capturas'}/07-bodega-amplia-movil.png`,fullPage:true});
  expect(errors).toEqual([]);
});

test('switching mission modes rebuilds geometry and keeps a single label layer', async ({page})=>{
  await page.request.post('/api/reset',{data:{makeup:false,orders:1,policy:'heuristic'}});
  await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();
  expect(await page.evaluate(()=>window.warehouseViewer.scene.layout.width)).toBe(17);
  await page.locator('#makeup').check();
  await expect.poll(()=>page.evaluate(()=>window.warehouseViewer.scene.layout.width)).toBe(25);
  await page.locator('#makeup').uncheck();
  await expect.poll(()=>page.evaluate(()=>window.warehouseViewer.scene.layout.width)).toBe(17);
  await expect(page.locator('#station-labels > *')).toHaveCount(5);
  await page.locator('#step').click();await expect(page.locator('#steps')).toHaveText('1');
});
