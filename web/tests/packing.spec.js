import {test,expect} from '@playwright/test';

test('confirmed delivery travels on a raised conveyor into a gift box, once',async({page})=>{
  let payload=await(await page.request.post('/api/reset',{data:{makeup:true,orders:1,seed:24,blocked:true,policy:'heuristic'}})).json();
  for(let n=0;!(payload.state.x===21&&payload.state.y===16&&payload.state.theta===1&&payload.state.v===0&&payload.state.lift.phase==='idle');n++){
    expect(n).toBeLessThan(250);expect(payload.done).toBe(false);
    payload=await(await page.request.post('/api/step',{data:{}})).json();
  }
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();
  await page.locator('#inspect-dispatch').click();
  await expect(page.locator('#packing-status')).toContainText('Esperando productos');
  expect(await page.evaluate(()=>window.warehouseViewer.scene.stockVisuals.packing.items.size)).toBe(0);
  await page.locator('#step').click();
  await expect(page.locator('.dispatch-panel')).toHaveAttribute('data-phase','conveying');
  await page.waitForFunction(()=>{
    const p=window.warehouseViewer.scene.stockVisuals.packing;
    const first=[...p.items.values()][0];return p.elapsed-first.at>1.1&&p.status().phase==='conveying';
  });
  const moving=await page.evaluate(()=>{
    const p=window.warehouseViewer.scene.stockVisuals.packing,first=[...p.items.values()][0];
    return {y:p.positionFor(first.sku,first.index).y,count:p.items.size,compact:p.compact,box:p.boxX};
  });
  expect(moving).toEqual({y:.75,count:3,compact:false,box:1});
  await page.screenshot({path:'/workspace/artifacts/warehouse-rush/09-cinta-transferencia.png'});
  await expect(page.locator('.dispatch-panel')).toHaveAttribute('data-phase','ready',{timeout:15000});
  await expect(page.locator('#packing-status')).toContainText('Caja preparada');
  const packed=await page.evaluate(()=>{
    const v=window.warehouseViewer, p=v.scene.stockVisuals.packing;
    return {status:p.status(),lid:p.lid.rotation.x,items:[...p.items.values()].map(i=>p.positionFor(i.sku,i.index).toArray()),
      ledger:v.state.state.order.lines.map(l=>({quantity:l.quantity,delivered:l.delivered})),done:v.state.done};
  });
  expect(packed.done).toBe(true);expect(packed.status.packed).toBe(3);expect(Math.abs(packed.lid)).toBeLessThan(.02);
  for(const [x,y,z] of packed.items){expect(x).toBeGreaterThan(.57);expect(x).toBeLessThan(1.43);expect(y).toBe(.47);expect(Math.abs(z)).toBeLessThan(.43);}
  expect(packed.ledger.every(l=>l.quantity===l.delivered)).toBe(true);
  await page.screenshot({path:'/workspace/artifacts/warehouse-rush/10-caja-lista.png'});
  await page.reload();await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('.dispatch-panel')).toHaveAttribute('data-phase','ready');
  expect(await page.evaluate(()=>window.warehouseViewer.scene.stockVisuals.packing.items.size)).toBe(3);
  await page.locator('#reset').click();
  await expect(page.locator('.dispatch-panel')).toHaveAttribute('data-phase','waiting');
  expect(await page.evaluate(()=>window.warehouseViewer.scene.stockVisuals.packing.items.size)).toBe(0);
  expect(errors).toEqual([]);
});
