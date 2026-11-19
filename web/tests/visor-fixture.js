// Las pruebas comparten explícitamente X-Sesion con la página, igual que un usuario.
// No se transforma la API ni se usan cookies para asociar peticiones y navegador.
import { test as base, expect } from '@playwright/test';
import { sessionKeyFor } from '../src/api-client.js';
export const API_BASE=process.env.WAREHOUSE_TEST_API_URL || 'http://127.0.0.1:7861';
export const test=base.extend({
  request:async({page,baseURL},use)=>{
    let session=null;
    async function send(method,path,options={}){
      try {
        if(new URL(page.url()).origin===new URL(baseURL).origin)session=await page.evaluate(key=>sessionStorage.getItem(key),sessionKeyFor(API_BASE)) || session;
      }catch{/* La página aún no ha navegado. */}
      const response=await page.request[method](new URL(path,API_BASE).href,{...options,headers:{...(session?{'X-Sesion':session}:{}),...options.headers}});
      if(response.ok()){
        const body=await response.json().catch(()=>null), next=response.headers()['x-sesion'] || body?.sesion_id;
        if(next){
          session=next;
          if(!page.url().startsWith(new URL(baseURL).origin)){
            await page.route('**/__fixture_session__',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Preparando sesión de prueba</title>'}));
            await page.goto(`${baseURL}/__fixture_session__`);
            await page.unroute('**/__fixture_session__');
          }
          await page.evaluate(({key,id})=>sessionStorage.setItem(key,id),{key:sessionKeyFor(API_BASE),id:session});
        }
      }
      return response;
    }
    await use({get:(p,o)=>send('get',p,o),post:(p,o)=>send('post',p,o),delete:(p,o)=>send('delete',p,o)});
  },
});
export {expect};
