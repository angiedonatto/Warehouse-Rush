import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const directory=new URL('../public/assets/products/',import.meta.url);await mkdir(directory,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--enable-webgl','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1040},deviceScaleFactor:1});
 await page.goto(process.env.WAREHOUSE_TEST_URL||'http://127.0.0.1:8080');await page.locator('#scene-loading').waitFor({state:'hidden'});
 await page.locator('#open-catalog').click();
 const skus=await page.locator('.product-card').evaluateAll(cards=>cards.map(card=>card.dataset.sku));
 for(const sku of skus){await page.locator(`[data-sku="${sku}"].product-card`).click();await page.locator('#product-canvas').screenshot({path:fileURLToPath(new URL(`${sku}.png`,directory))});}
 console.log(`Capturadas ${skus.length} miniaturas de los modelos reales.`);
} finally {await browser.close();}
