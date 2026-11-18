import { test, expect } from '@playwright/test';

test('upper shelf requires a raised platform, real pickup and lowering before travel', async ({ page, request }) => {
  let payload=await (await request.post('/api/reset',{data:{makeup:true,orders:1,seed:24,policy:'heuristic',blocked:true}})).json();
  const top=payload.state.order.lines.find(l=>l.height_m===2.6);
  expect(top).toBeTruthy();
  const initial=payload.state.inventory.products.find(p=>p.sku===top.sku).stock_total;
  for(let n=0;payload.state.lift.phase!=='ready'||payload.state.lift.height!==2.6;n++) {
    expect(n).toBeLessThan(250);expect(payload.done).toBe(false);
    payload=await(await request.post('/api/step',{data:{}})).json();
  }
  expect(payload.state.order.lines.find(l=>l.sku===top.sku).picked).toBe(0);
  const position=[payload.state.x,payload.state.y,payload.state.theta];
  await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#handling-status')).toContainText('2.60 m');
  await expect(page.locator('#handling-status')).toContainText('Altura alcanzada');
  await page.evaluate(()=>{
    const s=window.warehouseViewer.scene,p=s.robot.position;
    s.controls.minDistance=1;s.controls.enableDamping=false;s.controls.target.set(p.x,1.3,p.z);
    s.camera.position.set(p.x-4.5,4.2,p.z-2);s.controls.update();s.dirty=true;
  });
  await page.waitForFunction(()=>Math.abs(window.warehouseViewer.scene.stockVisuals.lift.height-2.6)<.01);
  await page.screenshot({path:'/workspace/artifacts/warehouse-rush/05-elevador-nivel-superior.png'});
  payload=await(await request.post('/api/step',{data:{}})).json();
  expect(payload.state.lift.phase).toBe('lowering');
  expect(payload.state.order.lines.find(l=>l.sku===top.sku).picked).toBe(top.quantity);
  expect(payload.state.inventory.products.find(p=>p.sku===top.sku).stock_total).toBe(initial-top.quantity);
  while(payload.state.lift.phase!=='idle') {
    payload=await(await request.post('/api/step',{data:{}})).json();
    expect([payload.state.x,payload.state.y,payload.state.theta]).toEqual(position);
  }
  expect(payload.state.lift.height).toBe(.55);
  while(!payload.done)payload=await(await request.post('/api/step',{data:{}})).json();
  expect(payload.info.success).toBe(true);
  expect(payload.state.lift.dispatch_visits).toBe(1);
});
